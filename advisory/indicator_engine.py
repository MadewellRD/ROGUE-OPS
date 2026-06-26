#
# indicator_engine.py
#
# Rolling Indicator Engine
# PHASE 59 + PHASE 4 (FEED ENRICHMENT) — REAL-TIME INDICATOR STATE
#
# RESPONSIBILITIES:
# - Maintain rolling indicator state
# - Consume MarketSnapshot ONLY (spot + optional OHLCV in snapshot.meta)
# - Emit IndicatorAssertion
#
# OHLCV (high/low/prev_close/volume) is read from snapshot.meta when the feed
# supplies it; ATR and VWAP are computed from it. When OHLCV is absent those
# values are None, which (by the signal engine's required_passed gate) blocks
# signals — fail-closed: we do not trade on indicators we cannot compute.
#
# NEVER: fetch vendor data, infer price, touch execution.
#

from dataclasses import dataclass
from typing import Dict, Optional

from market.market_data import MarketSnapshot
from advisory.indicator_authority import create_indicator_assertion


def _ema(prev: Optional[float], price: float, period: int) -> float:
    alpha = 2 / (period + 1)
    return price if prev is None else (price - prev) * alpha + prev


@dataclass
class IndicatorState:
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None

    rsi_gain_7: Optional[float] = None
    rsi_loss_7: Optional[float] = None
    rsi_gain_14: Optional[float] = None
    rsi_loss_14: Optional[float] = None

    last_price: Optional[float] = None

    macd_fast: Optional[float] = None
    macd_slow: Optional[float] = None
    macd_signal: Optional[float] = None

    # ATR (Wilder)
    atr: Optional[float] = None
    atr_last_close: Optional[float] = None

    # VWAP (incremental, volume-weighted)
    vwap_cum_pv: float = 0.0
    vwap_cum_vol: float = 0.0
    vwap_last_cum_vol: Optional[float] = None


ATR_PERIOD = 14
VWAP_EPSILON = 1e-9


class IndicatorEngine:
    """Brokerage-grade rolling indicator engine. One instance per symbol."""

    def __init__(self):
        self.state = IndicatorState()

    # --------------------------------------------------
    # ATR — Wilder smoothing of the true range
    # --------------------------------------------------

    def _update_atr(self, high, low, prev_close, price) -> Optional[float]:
        s = self.state
        if high is None or low is None:
            return None
        ref_close = prev_close
        if ref_close is None:
            ref_close = s.atr_last_close if s.atr_last_close is not None else price
        true_range = max(high - low, abs(high - ref_close), abs(low - ref_close))
        s.atr = true_range if s.atr is None else (s.atr * (ATR_PERIOD - 1) + true_range) / ATR_PERIOD
        s.atr_last_close = price
        return round(s.atr, 4)

    # --------------------------------------------------
    # VWAP — cumulative typical-price * incremental volume
    # --------------------------------------------------

    def _update_vwap(self, high, low, price, volume) -> Optional[float]:
        s = self.state
        if volume is None:
            return None
        typical = ((high + low + price) / 3) if (high is not None and low is not None) else price
        if s.vwap_last_cum_vol is None:
            delta_vol = float(volume)            # seed with the day's cumulative volume
        else:
            delta_vol = max(0.0, float(volume) - s.vwap_last_cum_vol)
        s.vwap_last_cum_vol = float(volume)
        s.vwap_cum_pv += typical * delta_vol
        s.vwap_cum_vol += delta_vol
        if s.vwap_cum_vol <= VWAP_EPSILON:
            return None
        return round(s.vwap_cum_pv / s.vwap_cum_vol, 4)

    # --------------------------------------------------
    # Update
    # --------------------------------------------------

    def update(self, snapshot: MarketSnapshot):
        price = snapshot.spot
        meta = snapshot.meta or {}
        high = meta.get("high")
        low = meta.get("low")
        prev_close = meta.get("prev_close")
        volume = meta.get("volume")

        state = self.state

        # EMA
        state.ema_9 = _ema(state.ema_9, price, 9)
        state.ema_21 = _ema(state.ema_21, price, 21)

        # RSI
        if state.last_price is not None:
            delta = price - state.last_price
            gain = max(delta, 0)
            loss = abs(min(delta, 0))
            state.rsi_gain_7 = gain if state.rsi_gain_7 is None else (state.rsi_gain_7 * 6 + gain) / 7
            state.rsi_loss_7 = loss if state.rsi_loss_7 is None else (state.rsi_loss_7 * 6 + loss) / 7
            state.rsi_gain_14 = gain if state.rsi_gain_14 is None else (state.rsi_gain_14 * 13 + gain) / 14
            state.rsi_loss_14 = loss if state.rsi_loss_14 is None else (state.rsi_loss_14 * 13 + loss) / 14
        state.last_price = price

        def _rsi(g, l):
            if g is None or l is None or l == 0:
                return None
            rs = g / l
            return round(100 - (100 / (1 + rs)), 4)

        rsi_7 = _rsi(state.rsi_gain_7, state.rsi_loss_7)
        rsi_14 = _rsi(state.rsi_gain_14, state.rsi_loss_14)

        # MACD histogram
        state.macd_fast = _ema(state.macd_fast, price, 12)
        state.macd_slow = _ema(state.macd_slow, price, 26)
        hist = None
        if state.macd_fast and state.macd_slow:
            macd = state.macd_fast - state.macd_slow
            state.macd_signal = _ema(state.macd_signal, macd, 9)
            if state.macd_signal:
                hist = round(macd - state.macd_signal, 4)

        # ATR + VWAP (from OHLCV when available)
        atr = self._update_atr(high, low, prev_close, price)
        vwap = self._update_vwap(high, low, price, volume)
        vwap_position = None
        if vwap is not None:
            vwap_position = "above" if price >= vwap else "below"

        required: Dict[str, object] = {
            "VWAP_Position": vwap_position,
            "EMA(9)": state.ema_9,
            "EMA(21)": state.ema_21,
            "RSI(7)": rsi_7,
            "RSI(14)": rsi_14,
            "MACD_Histogram": hist,
            "ATR": atr,
        }

        advisory: Dict[str, object] = {
            "Spot": price,
            "Session": snapshot.session,
            "VWAP": vwap,
        }

        return create_indicator_assertion(required=required, advisory=advisory)

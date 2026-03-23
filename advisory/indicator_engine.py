#
# indicator_engine.py
#
# Rolling Indicator Engine
# PHASE 59 — REAL-TIME INDICATOR STATE (BROKERAGE GRADE)
#
# RESPONSIBILITIES:
# - Maintain rolling indicator state
# - Consume MarketSnapshot ONLY
# - Emit IndicatorAssertion
#
# NEVER:
# - Fetch vendor data
# - Infer price
# - Touch execution
#

from dataclasses import dataclass
import datetime as dt
from typing import Dict

from market.market_data import MarketSnapshot
from advisory.indicator_authority import create_indicator_assertion


# ==================================================
# Helpers
# ==================================================

def _ema(prev: float | None, price: float, period: int) -> float:
    alpha = 2 / (period + 1)
    return price if prev is None else (price - prev) * alpha + prev


# ==================================================
# Indicator Engine
# ==================================================

@dataclass
class IndicatorState:
    ema_9: float | None = None
    ema_21: float | None = None

    rsi_gain_7: float | None = None
    rsi_loss_7: float | None = None
    rsi_gain_14: float | None = None
    rsi_loss_14: float | None = None

    last_price: float | None = None

    macd_fast: float | None = None
    macd_slow: float | None = None
    macd_signal: float | None = None


class IndicatorEngine:
    """
    Brokerage-grade rolling indicator engine.

    One instance per symbol.
    """

    def __init__(self):
        self.state = IndicatorState()

    # --------------------------------------------------
    # Update
    # --------------------------------------------------

    def update(self, snapshot: MarketSnapshot):
        price = snapshot.spot
        state = self.state

        # ----------------------------
        # EMA
        # ----------------------------
        state.ema_9 = _ema(state.ema_9, price, 9)
        state.ema_21 = _ema(state.ema_21, price, 21)

        # ----------------------------
        # RSI
        # ----------------------------
        if state.last_price is not None:
            delta = price - state.last_price
            gain = max(delta, 0)
            loss = abs(min(delta, 0))

            # RSI 7
            state.rsi_gain_7 = (
                gain if state.rsi_gain_7 is None
                else (state.rsi_gain_7 * 6 + gain) / 7
            )
            state.rsi_loss_7 = (
                loss if state.rsi_loss_7 is None
                else (state.rsi_loss_7 * 6 + loss) / 7
            )

            # RSI 14
            state.rsi_gain_14 = (
                gain if state.rsi_gain_14 is None
                else (state.rsi_gain_14 * 13 + gain) / 14
            )
            state.rsi_loss_14 = (
                loss if state.rsi_loss_14 is None
                else (state.rsi_loss_14 * 13 + loss) / 14
            )

        state.last_price = price

        def _rsi(g, l):
            if g is None or l is None or l == 0:
                return None
            rs = g / l
            return 100 - (100 / (1 + rs))

        rsi_7 = _rsi(state.rsi_gain_7, state.rsi_loss_7)
        rsi_14 = _rsi(state.rsi_gain_14, state.rsi_loss_14)

        # ----------------------------
        # MACD
        # ----------------------------
        state.macd_fast = _ema(state.macd_fast, price, 12)
        state.macd_slow = _ema(state.macd_slow, price, 26)

        macd = None
        signal = None
        hist = None

        if state.macd_fast and state.macd_slow:
            macd = state.macd_fast - state.macd_slow
            state.macd_signal = _ema(state.macd_signal, macd, 9)
            if state.macd_signal:
                signal = state.macd_signal
                hist = macd - signal

        # ----------------------------
        # Emit Assertion
        # ----------------------------

        required: Dict[str, float] = {
            "EMA(9)": state.ema_9,
            "EMA(21)": state.ema_21,
            "RSI(7)": rsi_7,
            "RSI(14)": rsi_14,
            "MACD": hist,
        }

        advisory: Dict[str, float] = {
            "Spot": price,
            "Session": snapshot.session,
        }

        return create_indicator_assertion(
            required=required,
            advisory=advisory,
        )

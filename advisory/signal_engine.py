#
# signal_engine.py
#
# Signal Engine — Structural Signal Eligibility
# PHASE 28 — REQUIRED INDICATOR PRESENCE ONLY (ATOMIC)
#
# Responsible for:
# - Determining whether a signal is ALLOWED TO EXIST
# - Enforcing REQUIRED indicator presence
# - Enforcing market/session eligibility
# - Emitting a PROPOSED ExecutionIntent + SignalContext
#
# Explicitly NOT responsible for:
# - Indicator interpretation
# - Trend or momentum logic
# - Confidence scoring
# - Risk evaluation
# - Entry authorization
#

from typing import Optional, Tuple

from market.market_data import MarketSnapshot
from execution.execution_contracts import ExecutionIntent, OptionSpec
from advisory.signal_context import create_signal_context
from advisory.indicator_authority import IndicatorAssertion


# ==================================================
# Phase 28 — Structural Constraints
# ==================================================

ALLOWED_SYMBOLS = {"SPY", "IWM"}
REQUIRED_SESSION = "REGULAR"
MIN_SPOT_PRICE = 10.0

DEFAULT_QTY = 1
ENTRY_ACTION = "BUY"
OPTION_RIGHT = "C"
STRIKE_ROUNDING = 1.0

# Required indicator keys for signal EXISTENCE. The feed now supplies OHLCV
# (Phase 4), so VWAP_Position and ATR are computed and required again. Signals
# are fail-closed: if any required indicator cannot be computed (e.g. the feed
# stops supplying OHLCV), required_passed is False and no signal is emitted.
REQUIRED_INDICATORS = {
    "VWAP_Position",
    "EMA(9)",
    "EMA(21)",
    "RSI(7)",
    "RSI(14)",
    "MACD_Histogram",
    "ATR",
}


# ==================================================
# Signal Engine
# ==================================================

class SignalEngine:
    """
    Deterministic signal existence authority.

    A signal CANNOT EXIST unless:
    - Market/session is eligible
    - Spot price is valid
    - REQUIRED indicator keys are present

    This engine DOES NOT interpret indicator values.
    """

    ENGINE_VERSION = "PHASE28_SIGNAL_EXISTENCE_V3"

    def evaluate(
        self,
        *,
        snapshot: MarketSnapshot,
        indicators: IndicatorAssertion,
    ) -> Optional[Tuple[ExecutionIntent, dict]]:
        """
        Evaluate whether a signal is permitted to exist.

        Returns:
            (ExecutionIntent, SignalContext) or None
        """

        # --------------------------------------------------
        # Market eligibility
        # --------------------------------------------------

        if snapshot.symbol not in ALLOWED_SYMBOLS:
            return None

        if snapshot.session != REQUIRED_SESSION:
            return None

        if snapshot.spot < MIN_SPOT_PRICE:
            return None

        # --------------------------------------------------
        # Indicator presence (FAIL-CLOSED)
        # --------------------------------------------------

        if not isinstance(indicators, IndicatorAssertion):
            return None

        if not REQUIRED_INDICATORS.issubset(indicators.required.keys()):
            return None

        # Do not emit on warmup/garbage: every required indicator value present.
        if not indicators.required_passed:
            return None

        # --------------------------------------------------
        # 0DTE option proposal (STRUCTURAL ONLY)
        # --------------------------------------------------

        expiry = snapshot.timestamp_utc.date().strftime("%Y%m%d")
        strike = round(snapshot.spot / STRIKE_ROUNDING) * STRIKE_ROUNDING

        option = OptionSpec(
            expiry=expiry,
            strike=float(strike),
            right=OPTION_RIGHT,
        )

        # --------------------------------------------------
        # SignalContext (PHASE 27 — STRUCTURAL ONLY)
        # --------------------------------------------------

        signal_context = create_signal_context(
            symbol=snapshot.symbol,
            timestamp_utc=snapshot.timestamp_utc,
            indicators=indicators.required,
            rules_passed={
                "phase": "28",
                "indicator_presence": "validated",
                "session": snapshot.session,
            },
            source=snapshot.source,
            engine_version=self.ENGINE_VERSION,
        )

        # --------------------------------------------------
        # Emit PROPOSED intent (authorization later)
        # --------------------------------------------------

        intent = ExecutionIntent.new(
            symbol=snapshot.symbol,
            qty=DEFAULT_QTY,
            action=ENTRY_ACTION,
            sec_type="OPT",
            strategy_tag="PHASE28_SIGNAL_PROPOSAL",
            option=option,
            signal_context_hash=signal_context.context_hash,
        )

        return intent, signal_context

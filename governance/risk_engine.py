#
# risk_engine.py
#
# Risk Engine v2 — Options-Aware, Delta-Aware
# PHASE C3 — DAILY LOSS HARD LOCK
#
# Supreme pre-trade AND session-survival authority.
#

from typing import Optional
import datetime as dt
import threading

from execution.execution_contracts import ExecutionIntent
from market.market_data import MarketSnapshot
from governance.kill_switch import engage_kill


# ==================================================
# Hard risk limits (institutional)
# ==================================================

ALLOWED_SYMBOLS = {"SPY", "IWM"}
ALLOWED_SECURITY_TYPE = "OPT"

MAX_CONTRACTS_PER_TRADE = 5
OPTION_MULTIPLIER = 100

# Max underlying-equivalent exposure per trade (USD)
MAX_DELTA_EXPOSURE_USD = 50_000

# Session controls
ALLOWED_SESSIONS = {"REGULAR"}

# Capital survival (HARD LOCK)
MAX_DAILY_LOSS_USD = 250


# ==================================================
# Daily PnL State (Process-Dominant)
# ==================================================

_LOCK = threading.Lock()
_DAILY_PNL_USD = 0.0
_PNL_DATE_UTC = None


# ==================================================
# Risk Engine v2
# ==================================================

class RiskEngineV2:
    """
    Deterministic, fail-closed risk authority.

    Responsibilities:
    - Pre-trade risk checks
    - Daily loss survival enforcement
    """

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def pre_trade_check(
        self,
        *,
        intent: ExecutionIntent,
        snapshot: MarketSnapshot,
        option_delta: Optional[float] = None,
    ) -> None:
        """
        Enforce all pre-trade and session survival constraints.
        """

        self._check_and_roll_session(snapshot)

        # ----------------------------
        # Daily loss hard lock
        # ----------------------------

        # Single source of truth for realized P&L lives in the daily-loss
        # governor; consult it so a prior breach blocks new entries.
        from capital.daily_loss_governor import is_breached as _daily_loss_breached
        if _daily_loss_breached():
            engage_kill(reason="DAILY_LOSS_LIMIT_BREACHED")
            raise RuntimeError("Daily loss limit breached — trading halted")

        # ----------------------------
        # Options-only enforcement
        # ----------------------------

        if intent.sec_type != ALLOWED_SECURITY_TYPE:
            raise RuntimeError("Only options trades are permitted")

        # ----------------------------
        # Symbol restriction
        # ----------------------------

        if intent.symbol not in ALLOWED_SYMBOLS:
            raise RuntimeError(f"Symbol {intent.symbol} not permitted")

        # ----------------------------
        # Quantity enforcement
        # ----------------------------

        if intent.quantity <= 0:
            raise RuntimeError("Quantity must be positive")

        if intent.quantity > MAX_CONTRACTS_PER_TRADE:
            raise RuntimeError(
                f"Quantity {intent.quantity} exceeds max {MAX_CONTRACTS_PER_TRADE}"
            )

        # ----------------------------
        # Market snapshot validation
        # ----------------------------

        if snapshot.symbol != intent.symbol:
            raise RuntimeError("Market snapshot symbol mismatch")

        if snapshot.spot <= 0:
            raise RuntimeError("Invalid spot price")

        # ----------------------------
        # Session enforcement
        # ----------------------------

        if snapshot.session not in ALLOWED_SESSIONS:
            raise RuntimeError(
                f"Trading not permitted in session {snapshot.session}"
            )

        # ----------------------------
        # Coarse notional guard
        # ----------------------------

        notional = snapshot.spot * OPTION_MULTIPLIER * intent.quantity
        if notional <= 0:
            raise RuntimeError("Computed notional invalid")

        # ----------------------------
        # Delta-aware exposure (OPTIONAL)
        # ----------------------------

        if option_delta is not None:
            if option_delta < 0 or option_delta > 1:
                raise RuntimeError("Option delta must be in [0, 1]")

            delta_exposure = (
                option_delta
                * intent.quantity
                * OPTION_MULTIPLIER
                * snapshot.spot
            )

            if delta_exposure > MAX_DELTA_EXPOSURE_USD:
                raise RuntimeError(
                    f"Delta exposure ${delta_exposure:,.0f} exceeds max "
                    f"${MAX_DELTA_EXPOSURE_USD:,.0f}"
                )

        # ----------------------------
        # Action sanity
        # ----------------------------

        if intent.action not in ("BUY", "SELL"):
            raise RuntimeError("Invalid trade action")

        return

    # --------------------------------------------------
    # PnL Accounting (Authoritative)
    # --------------------------------------------------

    @staticmethod
    def record_realized_pnl(pnl_usd: float, *, timestamp_utc: str) -> None:
        """
        Record realized PnL for the current session.

        Negative values represent losses.
        """

        global _DAILY_PNL_USD

        with _LOCK:
            _DAILY_PNL_USD += pnl_usd

            if _DAILY_PNL_USD <= -MAX_DAILY_LOSS_USD:
                engage_kill(reason="DAILY_LOSS_LIMIT_BREACHED")

    # --------------------------------------------------
    # Session rollover
    # --------------------------------------------------

    @staticmethod
    def _check_and_roll_session(snapshot: MarketSnapshot) -> None:
        """
        Reset PnL at the start of a new trading day (UTC).
        """

        global _PNL_DATE_UTC, _DAILY_PNL_USD

        current_date = snapshot.timestamp_utc.date()

        with _LOCK:
            if _PNL_DATE_UTC is None:
                _PNL_DATE_UTC = current_date
                _DAILY_PNL_USD = 0.0
                return

            if current_date != _PNL_DATE_UTC:
                _PNL_DATE_UTC = current_date
                _DAILY_PNL_USD = 0.0

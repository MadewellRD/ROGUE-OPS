#
# daily_loss_governor.py
#
# Daily Loss Governor
# PHASE 60 — REALIZED LOSS GOVERNANCE (AUTHORITATIVE)
#
# Responsible for:
# - Accumulating realized P&L during runtime
# - Enforcing MAX_DAILY_LOSS_USD
# - Engaging kill switch when breached
#
# Explicitly NOT responsible for:
# - Persistence
# - Strategy
# - Execution
# - Market data
#

import os
import datetime as dt

from governance.kill_switch import engage_kill


# ==================================================
# In-Memory State (Single-Process Authority)
# ==================================================

_REALIZED_PNL_USD = 0.0
_TRADING_DAY = None


# ==================================================
# Helpers
# ==================================================

def _current_trading_day() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


# ==================================================
# Public API
# ==================================================

def record_realized_pnl(*, pnl_usd: float) -> None:
    """
    Record realized P&L and enforce daily loss limits.

    FAILS CLOSED by engaging kill switch.
    """

    global _REALIZED_PNL_USD, _TRADING_DAY

    # CAPITAL ONLY
    if os.getenv("EXECUTION_MODE") != "CAPITAL":
        return

    today = _current_trading_day()

    # Reset on new UTC trading day
    if _TRADING_DAY != today:
        _TRADING_DAY = today
        _REALIZED_PNL_USD = 0.0

    _REALIZED_PNL_USD += pnl_usd

    max_loss = float(os.getenv("MAX_DAILY_LOSS_USD", "0"))

    if max_loss <= 0:
        return  # preflight already enforces validity

    if _REALIZED_PNL_USD <= -abs(max_loss):
        engage_kill(
            reason="DAILY_LOSS_LIMIT_BREACHED",
            metadata={
                "realized_pnl_usd": _REALIZED_PNL_USD,
                "limit_usd": max_loss,
                "day": today,
            },
        )

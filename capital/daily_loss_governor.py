#
# daily_loss_governor.py
#
# Daily Loss Governor
# PHASE 60 — REALIZED LOSS GOVERNANCE (AUTHORITATIVE)
#
# THE single source of truth for realized P&L and the daily-loss kill.
#
# Responsible for:
# - Accumulating realized P&L during runtime (all live modes)
# - Enforcing MAX_DAILY_LOSS_USD
# - Engaging the kill switch when breached (fail-closed)
# - Reporting breach state so the risk engine can block new entries
#
# Explicitly NOT responsible for: persistence, strategy, execution, market data.
#

import os
import datetime as dt

from governance.kill_switch import engage_kill


# ==================================================
# In-Memory State (Single-Process Authority)
# ==================================================

_REALIZED_PNL_USD = 0.0
_TRADING_DAY = None

# Default hard cap if MAX_DAILY_LOSS_USD is unset/invalid. We default to a
# NON-zero protective value rather than silently disabling the limit.
DEFAULT_MAX_DAILY_LOSS_USD = 250.0


# ==================================================
# Helpers
# ==================================================

def _current_trading_day() -> str:
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


def _max_loss() -> float:
    raw = os.getenv("MAX_DAILY_LOSS_USD", "")
    try:
        v = float(raw) if raw else DEFAULT_MAX_DAILY_LOSS_USD
    except ValueError:
        v = DEFAULT_MAX_DAILY_LOSS_USD
    return abs(v) if v != 0 else DEFAULT_MAX_DAILY_LOSS_USD


def _governed() -> bool:
    # SIM/REPLAY are not real money and are not governed; everything else is.
    return os.getenv("EXECUTION_MODE", "SIM") not in ("SIM", "REPLAY")


def _roll(today: str) -> None:
    global _TRADING_DAY, _REALIZED_PNL_USD
    if _TRADING_DAY != today:
        _TRADING_DAY = today
        _REALIZED_PNL_USD = 0.0


# ==================================================
# Public API
# ==================================================

def record_realized_pnl(*, pnl_usd: float) -> None:
    """
    Accumulate realized P&L and engage the kill switch on a daily-loss breach.
    FAILS CLOSED.
    """
    global _REALIZED_PNL_USD

    if not _governed():
        return

    _roll(_current_trading_day())
    _REALIZED_PNL_USD += pnl_usd

    if _REALIZED_PNL_USD <= -_max_loss():
        engage_kill(
            reason=(
                f"DAILY_LOSS_LIMIT_BREACHED:pnl={_REALIZED_PNL_USD:.2f}:"
                f"limit={_max_loss():.2f}"
            )
        )


def current_realized_pnl() -> float:
    _roll(_current_trading_day())
    return _REALIZED_PNL_USD


def is_breached() -> bool:
    """True if the governed daily-loss limit has been breached."""
    if not _governed():
        return False
    return current_realized_pnl() <= -_max_loss()


def reset() -> None:
    """Test/session helper: clear accumulated realized P&L for the day."""
    global _REALIZED_PNL_USD, _TRADING_DAY
    _REALIZED_PNL_USD = 0.0
    _TRADING_DAY = _current_trading_day()

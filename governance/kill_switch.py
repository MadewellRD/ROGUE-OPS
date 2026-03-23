#
# kill_switch.py
#
# Global Kill Switch Authority
# PHASE C2 — STATE-DOMINANT (HARDENED)
#
# This module is the SINGLE SOURCE OF TRUTH for kill state.
# It is fail-closed, auditable, and mechanically dominant.
#

import os
import threading
import datetime as dt


# ==================================================
# Kill State (Process-Dominant)
# ==================================================

_LOCK = threading.Lock()
_KILL_STATE = False
_KILL_REASON = None
_KILL_TIMESTAMP_UTC = None


# ==================================================
# Public API
# ==================================================

def engage_kill(reason: str) -> None:
    """
    Engage the global kill switch.

    This action is irreversible for the lifetime
    of the running process.
    """
    global _KILL_STATE, _KILL_REASON, _KILL_TIMESTAMP_UTC

    with _LOCK:
        if _KILL_STATE:
            return

        _KILL_STATE = True
        _KILL_REASON = reason
        _KILL_TIMESTAMP_UTC = _now_utc()


def kill_active() -> bool:
    """
    Determine whether the system is killed.

    Kill is active if:
    - Process kill state is engaged
    - OR environment kill flag is set

    This is FAIL-CLOSED.
    """
    if _KILL_STATE:
        return True

    env_flag = os.getenv("OPS_KILL_SWITCH", "false").lower() == "true"
    return env_flag


def kill_context() -> dict:
    """
    Return audit-safe kill context.
    """
    return {
        "killed": kill_active(),
        "reason": _KILL_REASON,
        "timestamp_utc": _KILL_TIMESTAMP_UTC,
        "env_flag": os.getenv("OPS_KILL_SWITCH", "false"),
    }


# ==================================================
# Helpers
# ==================================================

def _now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

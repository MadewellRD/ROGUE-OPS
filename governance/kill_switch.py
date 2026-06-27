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
        _write_kill_file(reason)


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

    if os.getenv("OPS_KILL_SWITCH", "false").lower() == "true":
        return True

    # Durable, cross-process kill: a file engaged by the operator / terminal.
    return _kill_file_present()


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


# ==================================================
# Durable, cross-process kill file
# ==================================================
#
# A separately-running operator surface (the terminal/console) cannot reach the
# in-process kill state of the trading loop. A file under ROGUE_OPS_HOME bridges
# that gap: the console writes it, the trading loop's kill_active() sees it on
# its next check and halts. This is strictly ADDITIVE to the fail-closed logic —
# it can only ever cause MORE kills, never fewer.

def _kill_file_path():
    try:
        from governance.paths import ops_home
        return ops_home() / "KILL"
    except Exception:
        return None


def _kill_file_present() -> bool:
    p = _kill_file_path()
    try:
        return bool(p and p.exists())
    except Exception:
        # Fail-closed: if we cannot tell, do not claim "not killed" on the file
        # path; the in-process / env checks above already ran.
        return False


def _write_kill_file(reason: str) -> None:
    p = _kill_file_path()
    if not p:
        return
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{_now_utc()} {reason}", encoding="utf-8")
    except Exception:
        pass


def clear_kill_file() -> bool:
    """
    Operator action: remove the durable kill file. This does NOT reset the
    in-process kill state (kill remains irreversible for a running process) —
    it only clears the durable flag so the NEXT process start is not killed.
    Returns True if a file was removed.
    """
    p = _kill_file_path()
    try:
        if p and p.exists():
            p.unlink()
            return True
    except Exception:
        pass
    return False

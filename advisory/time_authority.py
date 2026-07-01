# time_authority.py
#
# Live Session Time Authority
# PHASE 26 + PHASE 29 — ENTRY TIME & EXECUTION WINDOW JURISDICTION
#
# Single authoritative source for:
# - ENTRY eligibility (Phase 26)
# - Intraday execution window classification (Phase 29)
#
# Guarantees:
# - Deterministic (snapshot-driven)
# - Replay-safe
# - Auditable
# - ENTRY-only authority (EXIT always permitted elsewhere)
#
# Explicit exclusions:
# - No schedulers
# - No cron
# - No loops
# - No now()
#

import os
import datetime as dt
from typing import Tuple, Literal


# ==================================================
# Canonical UTC session boundaries (NYSE RTH)
# ==================================================

def _env_utc_time(name: str, default: dt.time) -> dt.time:
    """Optional UTC 'HH:MM' override (env) — lets a PAPER demo widen the entry
    window. CAPITAL leaves the default (14:30 ET cutoff)."""
    v = os.getenv(name)
    if v:
        try:
            hh, mm = (int(x) for x in v.split(":"))
            return dt.time(hh, mm)
        except Exception:
            pass
    return default


MARKET_OPEN_UTC = dt.time(13, 30)   # 09:30 ET
MIDDAY_UTC = dt.time(16, 0)         # 12:00 ET
LAST_ENTRY_UTC = _env_utc_time("ROGUE_LAST_ENTRY_UTC", dt.time(18, 30))  # 14:30 ET default
MARKET_CLOSE_UTC = dt.time(20, 0)   # 16:00 ET


# ==================================================
# Execution Window Classification (PHASE 29)
# ==================================================

ExecutionWindow = Literal[
    "FULL_ENABLE",
    "RESTRICTED",
    "ENTRY_FORBIDDEN",
]


def _effective_timestamp(timestamp_utc: dt.datetime) -> dt.datetime:
    """
    Resolve the effective timestamp for time authority evaluation.

    In SIM mode:
    - Injects a deterministic, market-open timestamp
    - Preserves replay safety
    - Does NOT affect PAPER or CAPITAL

    In all other modes:
    - Returns the original timestamp unchanged
    """

    if os.getenv("OPS_MODE") == "SIM":
        if timestamp_utc.tzinfo is None:
            raise RuntimeError("SIM timestamp must be tz-aware")

        return timestamp_utc.replace(
            hour=MARKET_OPEN_UTC.hour,
            minute=MARKET_OPEN_UTC.minute,
            second=0,
            microsecond=0,
        )

    return timestamp_utc


def get_execution_window(timestamp_utc: dt.datetime) -> ExecutionWindow:
    """
    Determine the execution window classification for a given timestamp.
    """

    ts = _effective_timestamp(timestamp_utc)

    if ts.tzinfo is None:
        return "ENTRY_FORBIDDEN"

    t = ts.time()

    if t < MARKET_OPEN_UTC:
        return "ENTRY_FORBIDDEN"

    if MARKET_OPEN_UTC <= t < MIDDAY_UTC:
        return "FULL_ENABLE"

    if MIDDAY_UTC <= t <= LAST_ENTRY_UTC:
        return "RESTRICTED"

    return "ENTRY_FORBIDDEN"


# ==================================================
# ENTRY Eligibility Authority (PHASE 26)
# ==================================================

def evaluate_entry_time(timestamp_utc: dt.datetime) -> Tuple[bool, str]:
    """
    Determine whether ENTRY is allowed at the given UTC timestamp.
    """

    ts = _effective_timestamp(timestamp_utc)

    if ts.tzinfo is None:
        return False, "TIMESTAMP_NOT_TZ_AWARE_UTC"

    t = ts.time()

    if t < MARKET_OPEN_UTC:
        return False, "BEFORE_MARKET_OPEN"

    if t > LAST_ENTRY_UTC:
        return False, "ENTRY_CUTOFF_EXCEEDED"

    if t >= MARKET_CLOSE_UTC:
        return False, "AFTER_MARKET_CLOSE"

    return True, "ENTRY_TIME_ALLOWED"

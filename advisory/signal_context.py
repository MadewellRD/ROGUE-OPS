#
# signal_context.py
#
# Signal Context — Immutable Justification Authority
# PHASE 27 — SIGNAL-TO-INTENT JUSTIFICATION (ATOMIC)
#
# Responsible for:
# - Capturing WHY a signal was produced
# - Binding indicators, thresholds, and timestamp immutably
# - Producing a deterministic hash for linkage
#
# Explicitly NOT responsible for:
# - Signal generation
# - Execution
# - Risk decisions
# - Market data fetching
#

from dataclasses import dataclass
from typing import Dict, Any
import hashlib
import json
import datetime as dt


# ==================================================
# Signal Context
# ==================================================

@dataclass(frozen=True)
class SignalContext:
    """
    Immutable justification for a trade signal.

    This object answers the question:
    'Why was this trade allowed to exist?'
    """

    symbol: str
    timestamp_utc: str

    # Indicator values asserted at decision time
    indicators: Dict[str, Any]

    # Thresholds or rules evaluated
    rules_passed: Dict[str, Any]

    # Origin metadata
    source: str               # e.g. "STEADY"
    engine_version: str       # e.g. "PHASE21_INDICATOR_SIGNAL"

    # Deterministic hash
    context_hash: str


# ==================================================
# Canonical Constructor
# ==================================================

def create_signal_context(
    *,
    symbol: str,
    timestamp_utc: dt.datetime,
    indicators: Dict[str, Any],
    rules_passed: Dict[str, Any],
    source: str,
    engine_version: str,
) -> SignalContext:
    """
    Create an immutable SignalContext.

    Fail-closed.
    Deterministic.
    Replay-safe.
    """

    if timestamp_utc.tzinfo is None:
        raise RuntimeError("SignalContext requires tz-aware UTC timestamp")

    ts = (
        timestamp_utc
        .astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    payload = {
        "symbol": symbol,
        "timestamp_utc": ts,
        "indicators": indicators,
        "rules_passed": rules_passed,
        "source": source,
        "engine_version": engine_version,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    context_hash = hashlib.sha256(encoded).hexdigest()

    return SignalContext(
        symbol=symbol,
        timestamp_utc=ts,
        indicators=indicators,
        rules_passed=rules_passed,
        source=source,
        engine_version=engine_version,
        context_hash=context_hash,
    )

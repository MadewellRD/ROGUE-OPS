# market_data.py
#
# Market Data Authority
# PHASE 20 + PHASE 28 — CANONICAL SNAPSHOT (SEALED)
#
# Responsible for:
# - Canonical spot price snapshot
# - Timestamp authority (UTC, tz-aware)
# - Deterministic replay support
# - Single source of truth for price + time
#
# AUTHORITY MODEL:
# - MarketSnapshot ASSERTS observed market truth
# - Adapters fetch raw data
# - Normalizer asserts validity and context
#
# This file NEVER:
# - Fetches data
# - Infers sessions
# - Applies strategy
# - Touches execution
#

from dataclasses import dataclass
from typing import Literal, Dict, Any
import datetime as dt


# ==================================================
# Type constraints
# ==================================================

# PHASE 28:
# Source = EXECUTION CONTEXT
# NOT vendor / provider
SourceType = Literal[
    "SIM",       # Synthetic / test
    "REPLAY",    # Historical replay
    "PAPER",     # Paper trading
    "LIVE",      # Live capital
]

SessionType = Literal[
    "PRE",
    "REGULAR",
    "POST",
    "CLOSED",
]


# ==================================================
# Canonical snapshot
# ==================================================

@dataclass(frozen=True)
class MarketSnapshot:
    """
    Immutable market snapshot.

    This object is the ONLY acceptable carrier
    of price and time inside ROGUE:OPS.

    All values are treated as ASSERTED TRUTH
    by downstream systems.
    """

    symbol: str
    spot: float
    timestamp_utc: dt.datetime   # tz-aware UTC
    session: SessionType
    source: SourceType
    meta: Dict[str, Any] | None = None


# ==================================================
# Authority constructor
# ==================================================

def create_market_snapshot(
    *,
    symbol: str,
    spot: float,
    timestamp_utc: dt.datetime,
    session: SessionType,
    source: SourceType,
    meta: Dict[str, Any] | None = None,
) -> MarketSnapshot:
    """
    Assert a canonical MarketSnapshot.

    All callers MUST supply:
    - tz-aware UTC timestamp
    - Explicit spot price
    - Explicit market session
    - Explicit execution-context source

    No defaults.
    No clocks.
    No inference.
    """

    # --------------------------------------------------
    # Symbol
    # --------------------------------------------------

    if not symbol or not isinstance(symbol, str):
        raise ValueError("Invalid symbol")

    # --------------------------------------------------
    # Spot sanity
    # --------------------------------------------------

    if not isinstance(spot, (int, float)) or spot <= 0:
        raise ValueError("Spot price must be positive")

    # --------------------------------------------------
    # Timestamp authority (ABSOLUTE)
    # --------------------------------------------------

    if not isinstance(timestamp_utc, dt.datetime):
        raise ValueError("timestamp_utc must be datetime")

    if timestamp_utc.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware UTC")

    timestamp_utc = timestamp_utc.astimezone(dt.timezone.utc).replace(
        microsecond=0
    )

    now_utc = dt.datetime.now(dt.timezone.utc)

    if timestamp_utc > now_utc + dt.timedelta(seconds=1):
        raise ValueError("Market snapshot timestamp is in the future")

    # --------------------------------------------------
    # Session validation
    # --------------------------------------------------

    if session not in ("PRE", "REGULAR", "POST", "CLOSED"):
        raise ValueError(f"Invalid market session: {session}")

    # --------------------------------------------------
    # Source validation (PHASE 28 SEALED)
    # --------------------------------------------------

    if source not in ("SIM", "REPLAY", "PAPER", "LIVE"):
        raise ValueError(f"Invalid market data source: {source}")

    # --------------------------------------------------
    # Emit snapshot
    # --------------------------------------------------

    return MarketSnapshot(
        symbol=symbol,
        spot=float(spot),
        timestamp_utc=timestamp_utc,
        session=session,
        source=source,
        meta=meta,
    )

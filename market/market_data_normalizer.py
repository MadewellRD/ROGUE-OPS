#
# market_data_normalizer.py
#
# Market Data Ingestion Normalization Authority
# PHASE 28 — CANONICAL DATA BOUNDARY (FINAL)
#
# This module is the ONLY legal authority for converting
# raw adapter data into a MarketSnapshot.
#
# Guarantees:
# - Deterministic normalization
# - Replay-safe behavior
# - Strict timestamp discipline
# - Explicit session assertion
#
# Adapters MUST call this module.
#

import datetime as dt
from typing import Literal

from market.market_data import MarketSnapshot, create_market_snapshot


# ==================================================
# Type constraints
# ==================================================

SessionType = Literal["PRE", "REGULAR", "POST", "CLOSED"]
SourceType = Literal["SIM", "REPLAY", "PAPER", "LIVE"]


# ==================================================
# Normalization Authority
# ==================================================

def normalize_market_data(
    *,
    symbol: str,
    spot: float,
    timestamp_utc: dt.datetime,
    session: SessionType,
    source: SourceType,
    high: float | None = None,
    low: float | None = None,
    prev_close: float | None = None,
    volume: float | None = None,
) -> MarketSnapshot:
    """
    Normalize asserted market data into a canonical MarketSnapshot.

    This function is:
    - Fail-closed
    - Deterministic
    - Replay-safe
    - Side-effect free

    Adapters are responsible ONLY for fetching.
    This function asserts truth.
    """

    # --------------------------------------------------
    # Symbol sanity
    # --------------------------------------------------
    if not symbol or not isinstance(symbol, str):
        raise RuntimeError("Invalid symbol")

    # --------------------------------------------------
    # Spot sanity
    # --------------------------------------------------
    if not isinstance(spot, (int, float)) or spot <= 0:
        raise RuntimeError("Invalid spot price")

    # --------------------------------------------------
    # Timestamp discipline (ABSOLUTE)
    # --------------------------------------------------
    if not isinstance(timestamp_utc, dt.datetime):
        raise RuntimeError("timestamp_utc must be datetime")

    if timestamp_utc.tzinfo is None:
        raise RuntimeError("timestamp_utc must be timezone-aware UTC")

    timestamp_utc = timestamp_utc.astimezone(dt.timezone.utc).replace(
        microsecond=0
    )

    # --------------------------------------------------
    # Session assertion
    # --------------------------------------------------
    if session not in ("PRE", "REGULAR", "POST", "CLOSED"):
        raise RuntimeError(f"Invalid market session: {session}")

    # --------------------------------------------------
    # Source assertion
    # --------------------------------------------------
    if source not in ("SIM", "REPLAY", "PAPER", "LIVE"):
        raise RuntimeError(f"Invalid market data source: {source}")

    # --------------------------------------------------
    # Emit canonical snapshot
    # --------------------------------------------------
    # Optional OHLCV carried in meta (Phase 4 feed enrichment).
    meta = {
        k: float(v)
        for k, v in {"high": high, "low": low, "prev_close": prev_close, "volume": volume}.items()
        if v is not None
    } or None

    return create_market_snapshot(
        symbol=symbol,
        spot=float(spot),
        timestamp_utc=timestamp_utc,
        session=session,
        source=source,
        meta=meta,
    )

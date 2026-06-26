# aavwap_authority.py
#
# Anchored VWAP Authority
# PHASE 37 — STRUCTURAL ANCHOR (ATOMIC)
#
# Responsible for:
# - Deterministic Anchored VWAP computation
# - Session-open anchoring
# - Position classification (above / below / at)
#
# This file DOES NOT:
# - Fetch data
# - Know about EMA, MACD, ATR
# - Authorize signals
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are validated OHLCV bars
# - Anchor is explicit and deterministic
# - Output is STRUCTURAL FACT ONLY
#

from dataclasses import dataclass
from typing import List
import datetime as dt


# ==================================================
# Types
# ==================================================

@dataclass(frozen=True)
class AAVWAPResult:
    aavwap_price: float
    position: str  # above | below | at


@dataclass(frozen=True)
class OHLCVBar:
    timestamp_utc: dt.datetime
    high: float
    low: float
    close: float
    volume: int


# ==================================================
# Anchored VWAP Computation
# ==================================================

def compute_aavwap(
    *,
    bars: List[OHLCVBar],
    spot_price: float,
    session_open_utc: dt.datetime,
) -> AAVWAPResult:
    """
    Compute Anchored VWAP from session open.

    Rules:
    - bars ordered MOST RECENT FIRST
    - session_open_utc is tz-aware UTC
    """

    if not bars:
        raise ValueError("No bars supplied")

    if session_open_utc.tzinfo is None:
        raise ValueError("session_open_utc must be timezone-aware UTC")

    pv_sum = 0.0
    vol_sum = 0.0

    for bar in bars:
        if bar.timestamp_utc < session_open_utc:
            break

        typical_price = (bar.high + bar.low + bar.close) / 3
        pv_sum += typical_price * bar.volume
        vol_sum += bar.volume

    if vol_sum == 0:
        raise ValueError("Zero volume in AAVWAP window")

    aavwap = pv_sum / vol_sum

    if spot_price > aavwap:
        position = "above"
    elif spot_price < aavwap:
        position = "below"
    else:
        position = "at"

    return AAVWAPResult(
        aavwap_price=round(aavwap, 6),
        position=position,
    )

# vwap_authority.py
#
# VWAP Authority
# PHASE 29 — STRUCTURAL VWAP COMPUTATION (ATOMIC)
#
# Responsible for:
# - Deterministic VWAP computation
# - Session-anchored accumulation
# - Replay-safe structural truth
#
# This file DOES NOT:
# - Fetch market data
# - Infer sessions
# - Perform indicator stacking
# - Authorize signals
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are assumed to be VALIDATED raw bars
# - Outputs are STRUCTURAL FACTS
# - Consumers may interpret, never modify
#

from dataclasses import dataclass
from typing import List, Literal
import datetime as dt


# ==================================================
# Types
# ==================================================

SessionType = Literal["PRE", "REGULAR", "POST"]


@dataclass(frozen=True)
class OHLCVBar:
    """
    Canonical OHLCV bar for VWAP computation.

    Assumptions:
    - All prices are floats
    - Volume is a positive integer
    - Timestamp is tz-aware UTC
    """

    timestamp_utc: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class VWAPResult:
    """
    Deterministic VWAP computation result.
    """

    vwap_price: float
    position: Literal["above", "below", "at"]


# ==================================================
# VWAP Computation (AUTHORITATIVE)
# ==================================================

def compute_vwap(
    *,
    bars: List[OHLCVBar],
    spot_price: float,
    session: SessionType,
) -> VWAPResult:
    """
    Compute VWAP for the current session.

    Rules:
    - Bars MUST belong to the same session
    - Bars MUST be ordered most-recent first OR last (order-independent)
    - VWAP is volume-weighted typical price
    - No smoothing, no averaging shortcuts
    """

    if not bars:
        raise ValueError("VWAP computation requires at least one bar")

    if spot_price <= 0:
        raise ValueError("Invalid spot price for VWAP computation")

    total_volume = 0.0
    total_vwap_value = 0.0

    for bar in bars:
        if bar.volume <= 0:
            continue  # zero-volume bars do not contribute

        typical_price = (bar.high + bar.low + bar.close) / 3.0
        total_vwap_value += typical_price * bar.volume
        total_volume += bar.volume

    if total_volume <= 0:
        raise ValueError("VWAP computation failed: zero effective volume")

    vwap_price = total_vwap_value / total_volume

    # ----------------------------------------------
    # Structural position (NO INTERPRETATION)
    # ----------------------------------------------

    if abs(spot_price - vwap_price) / vwap_price < 0.0005:
        position = "at"
    elif spot_price > vwap_price:
        position = "above"
    else:
        position = "below"

    return VWAPResult(
        vwap_price=round(vwap_price, 4),
        position=position,
    )

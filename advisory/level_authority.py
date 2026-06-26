# level_authority.py
#
# Price Level Authority
# PHASE 39 — STRUCTURAL CONTEXT (ATOMIC)
#
# Responsible for:
# - Prior Day High / Low / Close
# - Opening Range High / Low
#
# This file DOES NOT:
# - Fetch data
# - Know about VWAP, EMA, indicators
# - Authorize trades
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are validated OHLC bars
# - Output is STRUCTURAL FACT ONLY
#

from dataclasses import dataclass
from typing import List
import datetime as dt


# ==================================================
# Types
# ==================================================

@dataclass(frozen=True)
class OHLCBar:
    timestamp_utc: dt.datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class PriorDayLevels:
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class OpeningRangeLevels:
    high: float
    low: float


# ==================================================
# Prior Day Levels
# ==================================================

def compute_prior_day_levels(
    *,
    bars: List[OHLCBar],
    session_date: dt.date,
) -> PriorDayLevels:
    """
    Compute PDH / PDL / PDC from prior regular session.

    Rules:
    - bars ordered MOST RECENT FIRST
    - session_date is current trading day (ET)
    """

    prior_day = session_date - dt.timedelta(days=1)

    day_bars = [
        b for b in bars
        if b.timestamp_utc.date() == prior_day
    ]

    if not day_bars:
        raise ValueError("No bars found for prior day")

    high = max(b.high for b in day_bars)
    low = min(b.low for b in day_bars)

    # Last close of the day
    close_bar = max(day_bars, key=lambda b: b.timestamp_utc)

    return PriorDayLevels(
        high=round(high, 6),
        low=round(low, 6),
        close=round(close_bar.close, 6),
    )


# ==================================================
# Opening Range
# ==================================================

def compute_opening_range(
    *,
    bars: List[OHLCBar],
    session_open_utc: dt.datetime,
    duration_minutes: int = 15,
) -> OpeningRangeLevels:
    """
    Compute Opening Range High / Low.

    Default: first 15 minutes of regular session.
    """

    end_time = session_open_utc + dt.timedelta(minutes=duration_minutes)

    range_bars = [
        b for b in bars
        if session_open_utc <= b.timestamp_utc < end_time
    ]

    if not range_bars:
        raise ValueError("No bars in opening range window")

    high = max(b.high for b in range_bars)
    low = min(b.low for b in range_bars)

    return OpeningRangeLevels(
        high=round(high, 6),
        low=round(low, 6),
    )

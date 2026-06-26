# atr_authority.py
#
# ATR Authority
# PHASE 35 — VOLATILITY STRUCTURE (ATOMIC)
#
# Responsible for:
# - Deterministic ATR(14) computation
# - ATR state classification (expanding / contracting / stable)
#
# This file DOES NOT:
# - Fetch data
# - Know about VWAP, EMA, MACD
# - Authorize signals
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are validated OHLC bars
# - Output is volatility FACTS ONLY
#

from dataclasses import dataclass
from typing import List


# ==================================================
# Types
# ==================================================

@dataclass(frozen=True)
class OHLCBar:
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class ATRResult:
    atr_value: float
    atr_state: str  # expanding | contracting | stable


# ==================================================
# True Range
# ==================================================

def _true_range(current: OHLCBar, previous_close: float) -> float:
    return max(
        current.high - current.low,
        abs(current.high - previous_close),
        abs(current.low - previous_close),
    )


# ==================================================
# ATR Computation (AUTHORITATIVE)
# ==================================================

def compute_atr(
    *,
    bars: List[OHLCBar],
    period: int = 14,
    expansion_threshold: float = 1.15,
    contraction_threshold: float = 0.85,
) -> ATRResult:
    """
    Compute ATR and classify volatility state.

    Rules:
    - bars ordered MOST RECENT FIRST
    - len(bars) > period
    """

    if len(bars) <= period:
        raise ValueError("Insufficient bars for ATR computation")

    true_ranges: List[float] = []

    for i in range(len(bars) - 1):
        tr = _true_range(bars[i], bars[i + 1].close)
        true_ranges.append(tr)

    # Seed ATR with SMA
    atr = sum(true_ranges[:period]) / period

    # Wilder smoothing
    for tr in true_ranges[period:]:
        atr = ((atr * (period - 1)) + tr) / period

    # Compare against recent baseline
    recent_avg = sum(true_ranges[:period]) / period

    if atr > recent_avg * expansion_threshold:
        state = "expanding"
    elif atr < recent_avg * contraction_threshold:
        state = "contracting"
    else:
        state = "stable"

    return ATRResult(
        atr_value=round(atr, 6),
        atr_state=state,
    )

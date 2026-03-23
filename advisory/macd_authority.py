# macd_authority.py
#
# MACD Authority
# PHASE 33 — STRUCTURAL MOMENTUM COMPUTATION (ATOMIC)
#
# Responsible for:
# - Deterministic MACD computation (12, 26, 9)
# - Signal line computation
# - Histogram derivation (execution-gating)
# - Replay-safe momentum metrics
#
# This file DOES NOT:
# - Fetch data
# - Know about VWAP or EMA authority files
# - Authorize signals
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are validated close prices
# - EMA math is first-party
# - Outputs are MOMENTUM FACTS ONLY
#

from dataclasses import dataclass
from typing import List


# ==================================================
# Types
# ==================================================

@dataclass(frozen=True)
class MACDResult:
    macd: float
    signal: float
    histogram: float


# ==================================================
# Internal EMA (MACD-Scoped, Deterministic)
# ==================================================

def _ema(closes: List[float], period: int) -> float:
    """
    Deterministic EMA used exclusively for MACD.
    closes must be MOST RECENT FIRST.
    """
    multiplier = 2 / (period + 1)

    # Seed with SMA of oldest period
    ema = sum(closes[-period:]) / period

    # Walk forward toward most recent
    for price in reversed(closes[:-period]):
        ema = (price - ema) * multiplier + ema

    return ema


# ==================================================
# MACD Computation (AUTHORITATIVE)
# ==================================================

def compute_macd(
    *,
    closes: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """
    Compute MACD using standard parameters.

    Rules:
    - closes ordered MOST RECENT FIRST
    - slow_period < len(closes)
    - Deterministic EMA math only
    """

    if len(closes) <= slow_period:
        raise ValueError("Insufficient data for MACD computation")

    ema_fast = _ema(closes, fast_period)
    ema_slow = _ema(closes, slow_period)

    macd_line = ema_fast - ema_slow

    # Build MACD series for signal EMA
    macd_series: List[float] = []
    for i in range(len(closes) - slow_period):
        sub_closes = closes[i:]
        macd_series.append(
            _ema(sub_closes, fast_period) - _ema(sub_closes, slow_period)
        )

    signal_line = _ema(macd_series, signal_period)
    histogram = macd_line - signal_line

    return MACDResult(
        macd=round(macd_line, 6),
        signal=round(signal_line, 6),
        histogram=round(histogram, 6),
    )

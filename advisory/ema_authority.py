# ema_authority.py
#
# EMA Authority
# PHASE 31 — STRUCTURAL EMA COMPUTATION (ATOMIC)
#
# Responsible for:
# - Deterministic EMA computation
# - EMA slope derivation
# - Replay-safe structural trend metrics
#
# This file DOES NOT:
# - Fetch data
# - Know about VWAP
# - Know about RSI / MACD
# - Authorize signals
# - Touch execution
#
# AUTHORITY MODEL:
# - Inputs are validated close prices
# - Outputs are STRUCTURAL FACTS ONLY
#

from dataclasses import dataclass
from typing import List, Literal


# ==================================================
# Types
# ==================================================

SlopeType = Literal["up", "down", "flat"]


@dataclass(frozen=True)
class EMAResult:
    """
    Deterministic EMA computation result.
    """

    period: int
    ema_value: float
    slope: SlopeType


# ==================================================
# EMA Computation (AUTHORITATIVE)
# ==================================================

def compute_ema(*, closes: List[float], period: int) -> EMAResult:
    """
    Compute EMA and slope from close prices.

    Rules:
    - closes must be ordered MOST RECENT FIRST
    - period must be < len(closes)
    - No smoothing shortcuts
    """

    if period <= 1:
        raise ValueError("EMA period must be > 1")

    if len(closes) <= period:
        raise ValueError("Insufficient data for EMA computation")

    multiplier = 2 / (period + 1)

    # Seed EMA with simple average of the oldest period
    ema = sum(closes[-period:]) / period

    # Walk forward toward most recent close
    for price in reversed(closes[:-period]):
        ema = (price - ema) * multiplier + ema

    # Compute most recent EMA for slope determination
    prev_ema = ema
    ema_now = (closes[0] - ema) * multiplier + ema

    delta = ema_now - prev_ema

    if abs(delta) < 1e-6:
        slope: SlopeType = "flat"
    elif delta > 0:
        slope = "up"
    else:
        slope = "down"

    return EMAResult(
        period=period,
        ema_value=round(ema_now, 4),
        slope=slope,
    )

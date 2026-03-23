"""
Arbitrage Intake
PHASE 3 — External Signal Normalization → ObservationIntent

This module ingests arbitrage-style external signals and
converts them into ObservationIntent proposals.

CRITICAL CONSTRAINTS:
- NO execution authority
- NO LAW evaluation
- NO scheduling
- NO cadence enforcement
- NO broker or capital access

This module proposes intents ONLY.
"""

from dataclasses import dataclass
from typing import Optional

from strategy.observation.types import (
    ObservationIntent,
    ObservationScope,
)


# ==================================================
# EXTERNAL SIGNAL SHAPE (NORMALIZED)
# ==================================================

@dataclass(frozen=True)
class ArbitrageSignal:
    """
    Normalized representation of an external arbitrage signal.

    This is deliberately minimal to prevent signal overreach.
    """

    source: str
    requested_scope: ObservationScope
    requested_cadence_seconds: Optional[int]
    confidence: Optional[float] = None  # informational only


# ==================================================
# INTAKE LOGIC
# ==================================================

def arbitrage_signal_to_observation_intent(
    *,
    signal: ArbitrageSignal,
) -> ObservationIntent:
    """
    Convert an ArbitrageSignal into an ObservationIntent.

    This function is:
    - Deterministic
    - Replay-safe
    - Side-effect free

    It does NOT:
    - Evaluate LAW
    - Apply cadence rules
    - Schedule execution
    """

    return ObservationIntent(
        requested_scope=signal.requested_scope,
        requested_cadence_seconds=signal.requested_cadence_seconds,
        source=f"arbitrage:{signal.source}",
        confidence=signal.confidence,
    )

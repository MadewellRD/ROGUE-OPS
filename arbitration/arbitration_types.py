"""
Arbitration Types
PHASE 5 — Deterministic Intent Resolution

Defines canonical data structures for arbitration output.

Arbitration:
- Resolves conflicts
- Does NOT decide quality
- Does NOT execute
"""

from dataclasses import dataclass
from typing import Optional, Union

from execution.execution_contracts import ExecutionIntent
from strategy.observation.types import ObservationIntent


# ==================================================
# ARBITRATED INTENT
# ==================================================

ArbitratedIntent = Union[
    ExecutionIntent,
    ObservationIntent,
]


# ==================================================
# ARBITRATION RESULT
# ==================================================

@dataclass(frozen=True)
class ArbitrationResult:
    """
    Result of deterministic arbitration.

    If `intent` is None, arbitration resulted in NO ACTION.
    """

    intent: Optional[ArbitratedIntent]
    winning_strategy: Optional[str]
    reason: str

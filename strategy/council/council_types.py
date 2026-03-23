"""
Strategy Council Types
PHASE 4 — Intent Fan-Out, No Authority

Defines the canonical data structures used by the
Strategy Council.

The council:
- Aggregates intent proposals
- Preserves disagreement
- Has NO execution authority
"""

from dataclasses import dataclass
from typing import List, Optional, Union

from execution.execution_contracts import ExecutionIntent
from strategy.observation.types import ObservationIntent


# ==================================================
# COUNCIL INTENT UNION
# ==================================================

CouncilIntent = Union[
    ExecutionIntent,
    ObservationIntent,
]


# ==================================================
# COUNCIL PROPOSAL
# ==================================================

@dataclass(frozen=True)
class CouncilProposal:
    """
    Single strategy proposal.

    This is NOT a decision.
    This is NOT authoritative.
    """

    strategy_name: str
    intent: CouncilIntent
    rationale: Optional[str] = None


# ==================================================
# COUNCIL OUTPUT
# ==================================================

@dataclass(frozen=True)
class CouncilResult:
    """
    Result of a single council evaluation cycle.

    Contains all proposed intents, unmodified.
    """

    proposals: List[CouncilProposal]

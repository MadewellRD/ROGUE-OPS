"""
Arbitration Engine
PHASE 5 — Deterministic Conflict Resolution

This engine resolves multiple proposed intents into
zero or one arbitrated intent.

CRITICAL:
- No execution
- No LAW invocation
- No broker access
- No capital access
- Fully deterministic
"""

from typing import List

from arbitration.arbitration_types import ArbitrationResult
from strategy.council.council_types import CouncilResult, CouncilProposal
from execution.execution_contracts import ExecutionIntent
from strategy.observation.types import ObservationIntent


# ==================================================
# ARBITRATION ENGINE
# ==================================================

class DeterministicArbitrationEngine:
    """
    Resolve Council proposals deterministically.

    Resolution rules (hard-coded, intentional):
    1. Zero proposals → NO ACTION
    2. One proposal → pass through
    3. Multiple proposals:
       - ExecutionIntent > ObservationIntent
       - Same type → lexicographic strategy name
    """

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def arbitrate(
        self,
        *,
        council_result: CouncilResult,
    ) -> ArbitrationResult:
        proposals: List[CouncilProposal] = council_result.proposals

        # -----------------------------
        # RULE 1 — ZERO PROPOSALS
        # -----------------------------
        if not proposals:
            return ArbitrationResult(
                intent=None,
                winning_strategy=None,
                reason="No proposals submitted",
            )

        # -----------------------------
        # RULE 2 — SINGLE PROPOSAL
        # -----------------------------
        if len(proposals) == 1:
            proposal = proposals[0]
            return ArbitrationResult(
                intent=proposal.intent,
                winning_strategy=proposal.strategy_name,
                reason="Single proposal",
            )

        # -----------------------------
        # RULE 3 — MULTIPLE PROPOSALS
        # -----------------------------

        execution_proposals = [
            p for p in proposals if isinstance(p.intent, ExecutionIntent)
        ]

        if execution_proposals:
            candidates = execution_proposals
            reason = "ExecutionIntent takes precedence"
        else:
            candidates = [
                p for p in proposals if isinstance(p.intent, ObservationIntent)
            ]
            reason = "ObservationIntent fallback"

        # Deterministic tie-break
        candidates.sort(key=lambda p: p.strategy_name)

        winner = candidates[0]

        return ArbitrationResult(
            intent=winner.intent,
            winning_strategy=winner.strategy_name,
            reason=reason,
        )

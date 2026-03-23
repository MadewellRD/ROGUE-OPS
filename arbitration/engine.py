from typing import List

from arbitration.types import StrategyIntent, ArbitrationDecision
from arbitration.context import ArbitrationContext
from arbitration.merger import merge_intents
from arbitration.conflict_graph import detect_soft_conflicts
from arbitration.portfolio import portfolio_arbitrate
from arbitration.capital_gate import capital_gate
from arbitration.feedback import emit_strategy_feedback


class ArbitrationEngine:
    """
    Deterministic, non-authoritative arbitration engine.

    This engine:
    - Merges strategy intents
    - Resolves soft conflicts (advisory only)
    - Applies portfolio-level arbitration
    - Applies capital gating
    - Emits strategy feedback
    - Outputs ArbitrationDecision objects ONLY
    """

    def arbitrate(
        self,
        *,
        intents: List[StrategyIntent],
        context: ArbitrationContext,
    ) -> List[ArbitrationDecision]:

        if not intents:
            return []

        merged = merge_intents(intents)

        _conflicts = detect_soft_conflicts(merged)
        # Soft conflicts are advisory annotations only (v1)

        portfolio_decisions: List[ArbitrationDecision] = portfolio_arbitrate(
            merged
        )

        capital_filtered: List[ArbitrationDecision] = capital_gate(
            portfolio_decisions,
            capital_snapshot=context.capital_snapshot,
        )

        emit_strategy_feedback(capital_filtered)

        return capital_filtered

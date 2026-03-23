"""
Strategy Council Engine
PHASE 4 — Intent Fan-Out, Zero Authority

The Strategy Council coordinates multiple strategies
to produce a set of proposed intents.

CRITICAL:
- The council does NOT decide
- The council does NOT filter
- The council does NOT rank
- The council does NOT execute
- The council does NOT invoke LAW

It aggregates proposals only.
"""

from typing import List

from strategy.council.council_types import (
    CouncilProposal,
    CouncilResult,
)
from strategy.registry import StrategyRegistry
from market.types.market_snapshot import MarketSnapshot

from audit.council_audit_log import log_council_cycle


# ==================================================
# STRATEGY COUNCIL ENGINE
# ==================================================

class StrategyCouncilEngine:
    """
    Fan-out orchestration for strategy intent proposals.
    """

    def __init__(
        self,
        *,
        registry: StrategyRegistry,
    ):
        self._registry = registry

    # --------------------------------------------------
    # COUNCIL EVALUATION
    # --------------------------------------------------

    def evaluate(
        self,
        *,
        snapshot: MarketSnapshot,
    ) -> CouncilResult:
        """
        Run a single council evaluation cycle.

        Each registered strategy is evaluated independently.
        Failures in one strategy MUST NOT block others.
        """

        proposals: List[CouncilProposal] = []

        for strategy in self._registry.all():
            try:
                intents = strategy.evaluate(
                    snapshot=snapshot,
                    confidence_bias=0,
                )
            except Exception:
                # Strategy failures are isolated and ignored
                continue

            if not intents:
                continue

            for intent in intents:
                proposals.append(
                    CouncilProposal(
                        strategy_name=strategy.strategy_id,
                        intent=intent,
                        rationale=getattr(strategy, "rationale", None),
                    )
                )

        # --------------------------------------------------
        # PHASE 7.1 — COUNCIL OBSERVABILITY (NON-AUTHORITATIVE)
        # --------------------------------------------------
        log_council_cycle(
            snapshot_id=snapshot.snapshot_id,
            proposals=proposals,
        )

        return CouncilResult(proposals=proposals)

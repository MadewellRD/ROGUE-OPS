"""
Strategy Context Builder
SMC v1.1 — Deterministic Context Assembly (Corrected)

Responsible for:
- Building StrategyContext per MarketSnapshot
- Injecting confidence, portfolio, and capital hints
- Ensuring all registered strategies are represented
- Remaining fully replay-safe

Explicitly NOT responsible for:
- Strategy evaluation
- Arbitration
- Authorization
"""

import uuid
from typing import Dict

from strategy.types import StrategyContext
from strategy.feedback.store import StrategyFeedbackStore
from strategy.registry import StrategyRegistry


class StrategyContextBuilder:
    """
    The ONLY lawful constructor of StrategyContext.
    """

    def __init__(
        self,
        *,
        feedback_store: StrategyFeedbackStore,
        registry: StrategyRegistry,
    ) -> None:
        self._feedback = feedback_store
        self._registry = registry

    def build(
        self,
        *,
        snapshot_id: str,
        session: str,
    ) -> StrategyContext:
        """
        Build an immutable StrategyContext for a single evaluation cycle.
        """

        evaluation_id = f"ctx-{uuid.uuid4().hex}"

        # ---------------------------------------------
        # Strategy Confidence (Complete + Deterministic)
        # ---------------------------------------------
        confidence: Dict[str, int] = {}

        for strategy in self._registry.all():
            strategy_id = strategy.metadata.strategy_id
            confidence[strategy_id] = self._feedback.get_bias(strategy_id)

        # ---------------------------------------------
        # Portfolio / Capital (v1.1 defaults)
        # ---------------------------------------------
        portfolio_pressure = "NEUTRAL"
        capital_state = "NORMAL"

        return StrategyContext(
            evaluation_id=evaluation_id,
            snapshot_id=snapshot_id,
            strategy_confidence=confidence,
            portfolio_pressure=portfolio_pressure,
            capital_state=capital_state,
            session=session,
            metadata=None,
        )

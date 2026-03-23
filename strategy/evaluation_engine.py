"""
Strategy Evaluation Engine (SEE)
SMC v1.0 — Authoritative Implementation

Responsible for:
- Fan-out evaluation of registered StrategyModules
- Deterministic, snapshot-scoped execution
- Fault isolation and timing capture
- Producing non-authoritative StrategyIntents

Explicitly NOT responsible for:
- Authorization
- Risk enforcement
- Capital checks
- Broker interaction
- Strategy arbitration
"""

import time
import traceback
import uuid
from typing import List, Dict

from market.types.market_snapshot import MarketSnapshot
from strategy.registry import StrategyRegistry
from strategy.base import StrategyModule
from strategy.types import (
    IndicatorState,
    StrategyContext,
)
from arbitration.types import StrategyIntent


class StrategyEvaluationResult:
    """
    Immutable container for one evaluation cycle.
    """

    def __init__(
        self,
        *,
        evaluation_id: str,
        snapshot_id: str,
        intents: List[StrategyIntent],
        failures: Dict[str, str],
        timings_ms: Dict[str, float],
    ):
        self.evaluation_id = evaluation_id
        self.snapshot_id = snapshot_id
        self.intents = intents
        self.failures = failures
        self.timings_ms = timings_ms


class StrategyEvaluationEngine:
    """
    Canonical Strategy Evaluation Engine.

    This engine is the ONLY lawful executor of StrategyModules.
    """

    def __init__(
        self,
        *,
        registry: StrategyRegistry,
        max_eval_ms: int = 50,
    ):
        self._registry = registry
        self._max_eval_ms = max_eval_ms

    def evaluate(
        self,
        *,
        snapshot: MarketSnapshot,
        indicators: IndicatorState,
        context: StrategyContext,
    ) -> StrategyEvaluationResult:
        """
        Evaluate all registered strategies against a single MarketSnapshot.
        """

        evaluation_id = f"eval-{uuid.uuid4().hex}"
        intents: List[StrategyIntent] = []
        failures: Dict[str, str] = {}
        timings_ms: Dict[str, float] = {}

        strategies: List[StrategyModule] = self._registry.all()

        for strategy in strategies:
            strategy_id = strategy.strategy_id
            start = time.perf_counter()

            try:
                result = strategy.evaluate(
                    snapshot=snapshot,
                    confidence_bias=context.strategy_confidence.get(strategy_id, 0),
                )

                if result:
                    intents.extend(result)

            except Exception as exc:
                failures[strategy_id] = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                )

            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                timings_ms[strategy_id] = elapsed_ms

                if elapsed_ms > self._max_eval_ms:
                    failures[strategy_id] = (
                        f"Evaluation timeout: {elapsed_ms:.2f}ms "
                        f"(limit {self._max_eval_ms}ms)"
                    )

        return StrategyEvaluationResult(
            evaluation_id=evaluation_id,
            snapshot_id=snapshot.snapshot_id,
            intents=intents,
            failures=failures,
            timings_ms=timings_ms,
        )

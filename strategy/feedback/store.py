"""
Strategy Feedback Store
SMC v1.1 — Confidence Memory Layer

Responsible for:
- Accumulating immutable feedback events per strategy
- Producing a bounded confidence bias score

Explicitly NOT responsible for:
- Arbitration
- Strategy execution
- Risk decisions
- Capital allocation
"""

from collections import defaultdict
from typing import Dict, List

from .types import StrategyFeedbackEvent


class StrategyFeedbackStore:
    """
    Deterministic, replay-safe feedback accumulator.

    Produces a bounded confidence bias per strategy.
    """

    def __init__(self, *, max_events: int = 50) -> None:
        self._events: Dict[str, List[StrategyFeedbackEvent]] = defaultdict(list)
        self._max_events = max_events

    def record(self, event: StrategyFeedbackEvent) -> None:
        """
        Record a new feedback event for a strategy.

        Oldest events are discarded once max_events is exceeded.
        """
        events = self._events[event.strategy_id]
        events.append(event)

        if len(events) > self._max_events:
            self._events[event.strategy_id] = events[-self._max_events :]

    def get_bias(self, strategy_id: str) -> int:
        """
        Simple bounded scoring model (v1.0).

        Scoring:
        - ACCEPTED  -> +1
        - REJECTED  -> -1
        - PARTIAL   ->  0
        - NO_OP     ->  0

        Bias is clamped to [-5, +5].

        This score is advisory ONLY.
        """
        score = 0

        for event in self._events.get(strategy_id, []):
            if event.decision == "ACCEPTED":
                score += 1
            elif event.decision == "REJECTED":
                score -= 1

        return max(-5, min(5, score))

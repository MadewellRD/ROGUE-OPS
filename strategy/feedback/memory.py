from typing import Dict
from strategy.feedback.types import StrategyFeedback


class StrategyMemory:
    """
    Deterministic, in-process advisory memory.
    No persistence in v1.
    """

    def __init__(self) -> None:
        self._memory: Dict[str, int] = {}

    def apply(self, feedback: StrategyFeedback) -> None:
        delta = {
            "ACCEPTED": 1,
            "REJECTED": -2,
            "DOWNWEIGHTED": -1,
            "DEFERRED": 0,
        }.get(feedback.signal, 0)

        self._memory[feedback.strategy_id] = (
            self._memory.get(feedback.strategy_id, 0) + delta
        )

    def get_bias(self, strategy_id: str) -> int:
        return self._memory.get(strategy_id, 0)

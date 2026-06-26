from typing import List
from strategy.feedback.adapter import StrategyFeedbackAdapter
from strategy.feedback.types import StrategyFeedback


class StrategyFeedbackBus:
    """
    Central non-authoritative feedback bus.
    """

    def __init__(self, adapter: StrategyFeedbackAdapter):
        self._adapter = adapter

    def publish(self, feedbacks: List[StrategyFeedback]) -> None:
        for feedback in feedbacks:
            self._adapter.emit(feedback)

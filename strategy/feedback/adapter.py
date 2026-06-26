from strategy.feedback.memory import StrategyMemory
from strategy.feedback.types import StrategyFeedback


class StrategyFeedbackAdapter:
    """
    Thin adapter to keep feedback optional and suppressible.
    """

    def __init__(self, memory: StrategyMemory):
        self._memory = memory

    def emit(self, feedback: StrategyFeedback) -> None:
        self._memory.apply(feedback)

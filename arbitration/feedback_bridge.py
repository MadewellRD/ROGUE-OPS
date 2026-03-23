"""
Arbitration → Strategy Feedback Bridge

Responsible for:
- Recording arbitration outcomes
- Updating StrategyFeedbackStore

Explicitly NOT responsible for:
- Arbitration decisions
- Strategy evaluation
"""

import datetime as dt

from strategy.feedback.store import StrategyFeedbackStore
from strategy.feedback.types import StrategyFeedbackEvent


class ArbitrationFeedbackBridge:
    def __init__(
        self,
        *,
        feedback_store: StrategyFeedbackStore,
    ) -> None:
        self._store = feedback_store

    def record_outcome(
        self,
        *,
        strategy_id: str,
        snapshot_id: str,
        decision: str,
    ) -> None:
        self._store.record(
            StrategyFeedbackEvent(
                strategy_id=strategy_id,
                snapshot_id=snapshot_id,
                decision=decision,
                timestamp_utc=dt.datetime.utcnow(),
            )
        )

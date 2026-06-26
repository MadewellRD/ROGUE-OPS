"""
Arbitration → Strategy Feedback Emitter
SMC v1.0 — Deterministic, Replay-Safe

Responsible for:
- Translating arbitration decisions into StrategyFeedbackEvents
- Recording feedback into StrategyFeedbackStore

Explicitly NOT responsible for:
- Strategy confidence calculation
- Event aggregation
- Strategy evaluation
- Authorization or LAW interaction
"""

import datetime as dt
from typing import Iterable

from arbitration.types import ArbitrationDecision
from strategy.feedback.types import (
    StrategyFeedbackEvent,
    FeedbackDecision,
)
from strategy.feedback.store import StrategyFeedbackStore


def emit_strategy_feedback(
    *,
    decisions: Iterable[ArbitrationDecision],
    feedback_store: StrategyFeedbackStore,
    snapshot_id: str,
) -> None:
    """
    Emit deterministic feedback events based on arbitration outcomes.
    """

    now = dt.datetime.now(dt.timezone.utc)

    for decision in decisions:
        if decision.decision == "ACCEPT":
            outcome: FeedbackDecision = "ACCEPTED"
        elif decision.decision == "REJECT":
            outcome = "REJECTED"
        elif decision.decision == "PARTIAL":
            outcome = "PARTIAL"
        else:
            outcome = "NO_OP"

        event = StrategyFeedbackEvent(
            strategy_id=decision.intent.strategy_id,
            snapshot_id=snapshot_id,
            decision=outcome,
            timestamp_utc=now,
        )

        feedback_store.record(event)

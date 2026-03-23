"""
Arbitration → Strategy Feedback Emitter
SMC v1.0 — Deterministic, Replay-Safe

Responsible for:
- Translating arbitration results into StrategyFeedbackEvents
- Recording feedback into StrategyFeedbackStore

Explicitly NOT responsible for:
- Strategy confidence calculation
- Event aggregation
- Strategy evaluation
- Authorization or LAW interaction
"""

import datetime as dt
from typing import Iterable

from arbitration.types import ArbitratedIntent
from strategy.feedback.types import (
    StrategyFeedbackEvent,
    FeedbackDecision,
)
from strategy.feedback.store import StrategyFeedbackStore


def emit_strategy_feedback(
    *,
    decisions: Iterable[ArbitratedIntent],
    feedback_store: StrategyFeedbackStore,
    snapshot_id: str,
) -> None:
    """
    Emit deterministic feedback events based on arbitration outcomes.
    """

    now = dt.datetime.now(dt.timezone.utc)

    for arbitrated in decisions:
        if arbitrated.decision == "ACCEPT":
            outcome: FeedbackDecision = "ACCEPTED"
        elif arbitrated.decision == "REJECT":
            outcome = "REJECTED"
        elif arbitrated.decision == "ACCEPT_WITH_CONSTRAINT":
            outcome = "PARTIAL"
        else:
            outcome = "NO_OP"

        for strategy_id in arbitrated.intent.contributing_strategies:
            event = StrategyFeedbackEvent(
                strategy_id=strategy_id,
                snapshot_id=snapshot_id,
                decision=outcome,
                timestamp_utc=now,
            )

            feedback_store.record(event)

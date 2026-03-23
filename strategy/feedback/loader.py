import datetime as dt
from typing import Iterable

from .store import StrategyFeedbackStore
from .types import StrategyFeedbackEvent


def load_feedback_from_audit(
    *,
    audit_events: Iterable[dict],
    store: StrategyFeedbackStore,
) -> None:
    """
    Deterministically reconstruct feedback state from audit logs.
    """
    for record in audit_events:
        store.record(
            StrategyFeedbackEvent(
                strategy_id=record["strategy_id"],
                snapshot_id=record["snapshot_id"],
                decision=record["decision"],
                timestamp_utc=dt.datetime.fromisoformat(
                    record["timestamp_utc"]
                ),
            )
        )

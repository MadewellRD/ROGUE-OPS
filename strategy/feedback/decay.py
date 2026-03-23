"""
Strategy Confidence Decay Model
SMC v1.1 — Deterministic Soft Reset
"""

from strategy.feedback.store import StrategyFeedbackStore


def apply_confidence_decay(
    *,
    store: StrategyFeedbackStore,
    decay_step: int = 1,
) -> None:
    """
    Gradually decay confidence toward zero.

    This should be called on a slow cadence (e.g. hourly).
    """

    for strategy_id, events in store._events.items():
        if not events:
            continue

        # Reduce magnitude by decay_step
        bias = store.get_bias(strategy_id)

        if bias > 0:
            store._events[strategy_id] = events[:-decay_step]
        elif bias < 0:
            store._events[strategy_id] = events[:-decay_step]

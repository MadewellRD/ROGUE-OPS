"""
Strategy Feedback Types
SMC v1.1 — Strategy Confidence Signals

This module defines immutable feedback events emitted
by downstream arbitration and LAW layers.

These events are:
- Deterministic
- Replay-safe
- Non-authoritative

They are used ONLY to influence future strategy confidence.
"""

from dataclasses import dataclass
from typing import Literal
import datetime as dt


FeedbackDecision = Literal[
    "ACCEPTED",   # Fully authorized and executed
    "REJECTED",   # Explicitly denied by arbitration or LAW
    "PARTIAL",    # Partially accepted (e.g. scaled, trimmed)
    "NO_OP",      # Evaluated but not acted upon
]


@dataclass(frozen=True)
class StrategyFeedbackEvent:
    """
    Immutable feedback record for a single strategy decision.
    """

    strategy_id: str
    snapshot_id: str
    decision: FeedbackDecision
    timestamp_utc: dt.datetime

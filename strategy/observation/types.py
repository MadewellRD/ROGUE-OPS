"""
Observation Intent Types
SMC v1.0 — Canonical, Schema-Only Contracts

This module defines the immutable data structures used to
propose changes to market observation state.

RULES:
- NO runtime logic
- NO side effects
- NO imports from execution, market, or LAW layers
- NO authorization semantics
- Schema-only, replay-safe, auditable
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Literal
import uuid


# ==================================================
# OBSERVATION ACTION ENUM
# ==================================================

class ObservationAction(str, Enum):
    """
    Canonical observation actions.
    """

    START = "START"
    STOP = "STOP"
    MODIFY = "MODIFY"


# ==================================================
# OBSERVATION SCOPE ENUM
# ==================================================

class ObservationScope(str, Enum):
    """
    Scope of market observation.
    """

    NONE = "NONE"
    PRIMARY_ONLY = "PRIMARY_ONLY"
    MULTI_SYMBOL = "MULTI_SYMBOL"
    FULL_MARKET = "FULL_MARKET"


# ==================================================
# OBSERVATION INTENT (SCHEMA ONLY)
# ==================================================

@dataclass(frozen=True)
class ObservationIntent:
    """
    Non-authoritative proposal to change observation state.

    This intent does NOT:
    - start observation
    - stop observation
    - touch market data
    - imply permission

    It is a request only.
    """

    intent_id: str
    requester: Literal["STRATEGY", "AI", "SYSTEM"]
    action: ObservationAction
    scope: ObservationScope
    cadence_hint_seconds: Optional[int]
    reason: str

    @staticmethod
    def create(
        *,
        requester: Literal["STRATEGY", "AI", "SYSTEM"],
        action: ObservationAction,
        scope: ObservationScope,
        reason: str,
        cadence_hint_seconds: Optional[int] = None,
    ) -> "ObservationIntent":
        """
        Deterministic factory for ObservationIntent.
        """
        return ObservationIntent(
            intent_id=f"obs-{uuid.uuid4().hex}",
            requester=requester,
            action=action,
            scope=scope,
            cadence_hint_seconds=cadence_hint_seconds,
            reason=reason,
        )

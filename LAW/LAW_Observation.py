"""
LAW_Observation
SMC v1.0 — Read-Only Authority Evaluation

This module defines the authoritative evaluation of ObservationIntent.
It does NOT execute observation, mutate runtime state, or call vendors.

ROLE:
- Evaluate whether an observation request is permitted
- Produce an auditable, replay-safe decision
- Enforce doctrine and safety constraints

RULES:
- NO runtime side effects
- NO market data access
- NO execution authority
- Deterministic and idempotent
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from strategy.observation.types import (
    ObservationIntent,
    ObservationAction,
    ObservationScope,
)


# ==================================================
# LAW DECISION ENUM
# ==================================================

class ObservationDecisionStatus(str, Enum):
    """
    Canonical LAW outcomes for observation requests.
    """

    ALLOW = "ALLOW"
    DENY = "DENY"
    LIMIT = "LIMIT"


# ==================================================
# LAW DECISION STRUCT
# ==================================================

@dataclass(frozen=True)
class ObservationDecision:
    """
    Authoritative evaluation result for an ObservationIntent.
    """

    status: ObservationDecisionStatus
    effective_scope: ObservationScope
    effective_cadence_seconds: Optional[int]
    reason: str


# ==================================================
# LAW EVALUATION (READ-ONLY)
# ==================================================

def evaluate_observation_intent(
    *,
    intent: ObservationIntent,
    system_kill_active: bool,
    market_session: Optional[str],
    observation_already_active: bool,
) -> ObservationDecision:
    """
    Evaluate an ObservationIntent under LAW.

    Inputs are explicit to preserve replay safety and determinism.
    """

    # ----------------------------------------------
    # HARD DENY — SYSTEM KILL
    # ----------------------------------------------
    if system_kill_active:
        return ObservationDecision(
            status=ObservationDecisionStatus.DENY,
            effective_scope=ObservationScope.NONE,
            effective_cadence_seconds=None,
            reason="System kill switch active",
        )

    # ----------------------------------------------
    # HARD DENY — STOP REQUEST ALWAYS ALLOWED
    # ----------------------------------------------
    if intent.action == ObservationAction.STOP:
        return ObservationDecision(
            status=ObservationDecisionStatus.ALLOW,
            effective_scope=ObservationScope.NONE,
            effective_cadence_seconds=None,
            reason="Observation stop permitted",
        )

    # ----------------------------------------------
    # DENY — DUPLICATE START
    # ----------------------------------------------
    if (
        intent.action == ObservationAction.START
        and observation_already_active
    ):
        return ObservationDecision(
            status=ObservationDecisionStatus.DENY,
            effective_scope=ObservationScope.NONE,
            effective_cadence_seconds=None,
            reason="Observation already active",
        )

    # ----------------------------------------------
    # LIMIT — OUTSIDE MARKET SESSION
    # ----------------------------------------------
    if market_session in ("CLOSED", None):
        return ObservationDecision(
            status=ObservationDecisionStatus.LIMIT,
            effective_scope=ObservationScope.PRIMARY_ONLY,
            effective_cadence_seconds=300,
            reason="Market closed — observation limited",
        )

    # ----------------------------------------------
    # DEFAULT — ALLOW AS REQUESTED
    # ----------------------------------------------
    return ObservationDecision(
        status=ObservationDecisionStatus.ALLOW,
        effective_scope=intent.scope,
        effective_cadence_seconds=intent.cadence_hint_seconds,
        reason="Observation permitted under LAW",
    )

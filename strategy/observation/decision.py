"""
Observation Decision Pipeline
SMC v1.1 — Intent → LAW → Audit → Controller (Idle Wiring)

This module defines the ONLY lawful execution path for
evaluating ObservationIntent under LAW and handing the
decision to runtime (inert).
"""

from typing import Optional

from strategy.observation.types import ObservationIntent
from strategy.observation.envelope import ObservationDecisionEnvelope

from LAW.LAW_Observation import evaluate_observation_intent

from audit.observation_audit_log import (
    log_observation_intent_proposed,
    log_observation_law_decision,
)

from observation.controller import ObservationController


# ==================================================
# DECISION ENTRYPOINT (AUTHORITATIVE)
# ==================================================

def evaluate_and_dispatch_observation_intent(
    *,
    intent: ObservationIntent,
    system_kill_active: bool,
    market_session: Optional[str],
    observation_already_active: bool,
    controller: ObservationController,
) -> ObservationDecisionEnvelope:
    """
    Evaluate an ObservationIntent under LAW and dispatch the
    resulting decision to the ObservationController.

    Deterministic. Replay-safe. No runtime effects.
    """

    # -------------------------------
    # AUDIT — INTENT PROPOSED
    # -------------------------------
    log_observation_intent_proposed(intent=intent)

    # -------------------------------
    # LAW EVALUATION
    # -------------------------------
    law_decision = evaluate_observation_intent(
        intent=intent,
        system_kill_active=system_kill_active,
        market_session=market_session,
        observation_already_active=observation_already_active,
    )

    # -------------------------------
    # ENVELOPE CONSTRUCTION
    # -------------------------------
    envelope = ObservationDecisionEnvelope.from_law_decision(
        intent=intent,
        status=law_decision.status,
        effective_scope=law_decision.effective_scope,
        effective_cadence_seconds=law_decision.effective_cadence_seconds,
        reason=law_decision.reason,
    )

    # -------------------------------
    # AUDIT — LAW DECISION
    # -------------------------------
    log_observation_law_decision(
        intent=intent,
        decision=envelope,
    )

    # -------------------------------
    # CONTROLLER HANDOFF (NO-OP)
    # -------------------------------
    controller.apply_decision(decision=envelope)

    return envelope

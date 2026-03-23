"""
Observation Audit Log
SMC v1.0 — Non-Authoritative Traceability

This module records proposals and LAW decisions related to
market observation governance.

ROLE:
- Provide audit visibility
- Support replay and post-mortem analysis
- Never influence runtime behavior

RULES:
- NO side effects beyond logging
- NO authorization
- NO runtime control
"""

import datetime as dt
from typing import Optional

from strategy.observation.types import ObservationIntent
from LAW.LAW_Observation import ObservationDecision


# ==================================================
# OBSERVATION INTENT PROPOSAL LOG
# ==================================================

def log_observation_intent_proposed(
    *,
    intent: ObservationIntent,
) -> None:
    """
    Record that an ObservationIntent was proposed.
    """

    ts = dt.datetime.now(dt.timezone.utc).isoformat()

    print(
        "[AUDIT][OBSERVATION][INTENT_PROPOSED]",
        {
            "timestamp_utc": ts,
            "intent_id": intent.intent_id,
            "requester": intent.requester,
            "action": intent.action,
            "scope": intent.scope,
            "cadence_hint_seconds": intent.cadence_hint_seconds,
            "reason": intent.reason,
        },
    )


# ==================================================
# LAW DECISION LOG
# ==================================================

def log_observation_law_decision(
    *,
    intent: ObservationIntent,
    decision: ObservationDecision,
) -> None:
    """
    Record the LAW evaluation outcome for an ObservationIntent.
    """

    ts = dt.datetime.now(dt.timezone.utc).isoformat()

    print(
        "[AUDIT][OBSERVATION][LAW_DECISION]",
        {
            "timestamp_utc": ts,
            "intent_id": intent.intent_id,
            "status": decision.status,
            "effective_scope": decision.effective_scope,
            "effective_cadence_seconds": decision.effective_cadence_seconds,
            "reason": decision.reason,
        },
    )

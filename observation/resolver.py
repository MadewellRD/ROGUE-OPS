"""
Observation Scope Resolver
SMC v1.0 — Deterministic, Read-Only Wiring

This module resolves an authorized ObservationDecisionEnvelope
into a concrete list of symbols to observe.

ROLE:
- Bind ObservationScope to explicit symbols
- Enforce fail-closed behavior
- Preserve replay safety and auditability

RULES:
- NO vendor access
- NO market discovery
- NO runtime state mutation
- NO background execution
"""

from typing import List, Optional

from strategy.observation.decision import (
    ObservationDecisionEnvelope,
    evaluate_and_dispatch_observation_intent,
)
from strategy.observation.types import (
    ObservationScope,
    ObservationIntent,
)

from observation.scheduler import ObservationScheduler
from observation.cadence_policy import ObservationCadencePolicy
from observation.controller import ObservationController


# ==================================================
# RESOLUTION ERROR
# ==================================================

class ObservationResolutionError(Exception):
    """
    Raised when observation scope cannot be safely resolved.
    """
    pass


# ==================================================
# SCOPE RESOLUTION (UNCHANGED — DO NOT MODIFY)
# ==================================================

def resolve_observation_symbols(
    *,
    decision: ObservationDecisionEnvelope,
    primary_symbol: Optional[str],
    explicit_symbols: Optional[List[str]] = None,
) -> List[str]:
    """
    Resolve an ObservationDecisionEnvelope into concrete symbols.

    This function is:
    - Deterministic
    - Replay-safe
    - Fail-closed

    It assumes NO market discovery capability.
    """

    scope = decision.effective_scope

    if scope == ObservationScope.NONE:
        return []

    if scope == ObservationScope.PRIMARY_ONLY:
        if not primary_symbol:
            raise ObservationResolutionError(
                "PRIMARY_ONLY scope requires primary_symbol"
            )
        return [primary_symbol]

    if scope == ObservationScope.MULTI_SYMBOL:
        if not explicit_symbols:
            raise ObservationResolutionError(
                "MULTI_SYMBOL scope requires explicit_symbols"
            )
        return list(explicit_symbols)

    if scope == ObservationScope.FULL_MARKET:
        raise ObservationResolutionError(
            "FULL_MARKET scope must be pre-expanded upstream"
        )

    raise ObservationResolutionError(
        f"Unrecognized observation scope: {scope}"
    )


# ==================================================
# PHASE 2 — OBSERVATION ACTIVATION ORCHESTRATION
# ==================================================

def maybe_propose_observation_intent(
    *,
    scheduler: ObservationScheduler,
    cadence_policy: ObservationCadencePolicy,
    controller: ObservationController,
    requested_scope: ObservationScope,
    requested_cadence_seconds: Optional[int],
    market_session: Optional[str],
    system_kill_active: bool,
    observation_already_active: bool,
) -> Optional[ObservationDecisionEnvelope]:
    """
    Phase 2 activation entrypoint.

    This function:
    - Gates observation proposal by time & session
    - Normalizes cadence
    - Proposes ObservationIntent
    - Hands off to LAW
    - Advances scheduler ONLY on LAW acceptance

    It does NOT:
    - Resolve symbols
    - Execute observations
    - Produce side effects
    """

    if not scheduler.observation_allowed(
        market_session=market_session
    ):
        return None

    cadence = cadence_policy.normalize(
        requested_cadence_seconds=requested_cadence_seconds
    )

    intent = ObservationIntent(
        requested_scope=requested_scope,
        requested_cadence_seconds=cadence.cadence_seconds,
    )

    envelope = evaluate_and_dispatch_observation_intent(
        intent=intent,
        system_kill_active=system_kill_active,
        market_session=market_session,
        observation_already_active=observation_already_active,
        controller=controller,
    )

    if envelope.status == "AUTHORIZED":
        scheduler.mark_observation_proposed()

    return envelope

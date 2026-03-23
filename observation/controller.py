"""
Observation Controller (Null Implementation)
SMC v1.0 — Inert Runtime Boundary

This controller represents the ONLY lawful runtime receiver
of observation authorization decisions.

CURRENT BEHAVIOR:
- Accepts ObservationDecisionEnvelope
- Stores last decision
- Performs NO observation
- Calls NO vendors
- Starts NO loops

This file intentionally does almost nothing.
"""

from typing import Optional, TYPE_CHECKING

from strategy.observation.types import ObservationScope
from LAW.LAW_Observation import ObservationDecisionStatus

if TYPE_CHECKING:
    from strategy.observation.decision import ObservationDecisionEnvelope


class ObservationController:
    """
    No-op observation controller.

    This class is intentionally inert.
    """

    def __init__(self) -> None:
        self._last_decision: Optional["ObservationDecisionEnvelope"] = None

    def apply_decision(
        self,
        *,
        decision: "ObservationDecisionEnvelope",
    ) -> None:
        """
        Apply an observation decision.

        This method records the decision but does not act on it.
        """

        self._last_decision = decision

        print(
            "[OBSERVATION][CONTROLLER][DECISION_APPLIED]",
            {
                "intent_id": decision.intent_id,
                "status": decision.status,
                "scope": decision.effective_scope,
                "cadence": decision.effective_cadence_seconds,
                "reason": decision.reason,
            },
        )

    def current_status(self) -> ObservationDecisionStatus:
        """
        Return the current observation status.
        """

        if self._last_decision is None:
            return ObservationDecisionStatus.DENY

        return self._last_decision.status

    def current_scope(self) -> ObservationScope:
        """
        Return the current effective observation scope.
        """

        if self._last_decision is None:
            return ObservationScope.NONE

        return self._last_decision.effective_scope

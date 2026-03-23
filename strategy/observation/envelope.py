"""
Observation Decision Envelope
Authoritative, Immutable Decision Artifact

This envelope represents the FINAL outcome of LAW evaluation
for an ObservationIntent.

It is the ONLY object allowed to cross the boundary between:
LAW → Audit → Controller
"""

from dataclasses import dataclass
from typing import Optional

from strategy.observation.types import ObservationIntent


@dataclass(frozen=True)
class ObservationDecisionEnvelope:
    """
    Immutable decision record produced by LAW_Observation.

    This object is:
    - Deterministic
    - Replay-safe
    - Audit-friendly
    - Non-executable by itself
    """

    intent: ObservationIntent
    status: str
    effective_scope: Optional[str]
    effective_cadence_seconds: Optional[int]
    reason: Optional[str]

    @classmethod
    def from_law_decision(
        cls,
        *,
        intent: ObservationIntent,
        status: str,
        effective_scope: Optional[str],
        effective_cadence_seconds: Optional[int],
        reason: Optional[str],
    ) -> "ObservationDecisionEnvelope":
        """
        Canonical constructor from LAW decision output.
        """

        return cls(
            intent=intent,
            status=status,
            effective_scope=effective_scope,
            effective_cadence_seconds=effective_cadence_seconds,
            reason=reason,
        )

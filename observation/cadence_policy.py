"""
Observation Cadence Policy
PHASE 2 — Cadence Normalization & Enforcement

This module defines HOW OFTEN observations are permitted
to be proposed.

It does NOT:
- schedule observations
- track time
- create intents
- evaluate LAW
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ObservationCadence:
    """
    Normalized cadence definition.

    All values are explicit and bounded to prevent
    runaway observation loops.
    """

    cadence_seconds: int


class ObservationCadencePolicy:
    """
    Canonical cadence policy for observations.

    Responsibilities:
    - Enforce minimum cadence
    - Enforce maximum cadence
    - Normalize undefined cadence requests
    """

    DEFAULT_CADENCE_SECONDS = 60
    MIN_CADENCE_SECONDS = 30
    MAX_CADENCE_SECONDS = 900  # 15 minutes

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def normalize(
        self,
        *,
        requested_cadence_seconds: Optional[int],
    ) -> ObservationCadence:
        """
        Normalize a requested cadence into a safe, bounded cadence.

        Deterministic.
        No side effects.
        """

        if requested_cadence_seconds is None:
            cadence = self.DEFAULT_CADENCE_SECONDS
        else:
            cadence = requested_cadence_seconds

        if cadence < self.MIN_CADENCE_SECONDS:
            cadence = self.MIN_CADENCE_SECONDS

        if cadence > self.MAX_CADENCE_SECONDS:
            cadence = self.MAX_CADENCE_SECONDS

        return ObservationCadence(cadence_seconds=cadence)

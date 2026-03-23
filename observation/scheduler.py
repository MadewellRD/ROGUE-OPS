"""
Observation Scheduler
PHASE 2 — Activation Layer (Time & Session Gating Only)

This module determines WHEN an observation is permitted
to be proposed.

It does NOT:
- interpret market data
- create intents
- evaluate LAW
- trigger execution
"""

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ObservationScheduleState:
    """
    Minimal scheduler state.

    This state is intentionally small to ensure:
    - determinism
    - replay safety
    - auditability
    """

    last_observation_ts: Optional[float] = None


class ObservationScheduler:
    """
    Authoritative scheduler for observation proposals.

    Responsibilities:
    - Enforce minimum cadence
    - Enforce session validity
    - Prevent rapid re-proposal

    This class answers ONLY:
    'Is an observation allowed to be proposed now?'
    """

    def __init__(
        self,
        *,
        min_cadence_seconds: int,
    ):
        self._min_cadence_seconds = min_cadence_seconds
        self._state = ObservationScheduleState()

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def observation_allowed(
        self,
        *,
        now_ts: Optional[float] = None,
        market_session: Optional[str],
    ) -> bool:
        """
        Determine whether an observation proposal is allowed.

        Deterministic:
        - No randomness
        - No side effects

        Returns:
            bool — permission only, not intent
        """

        # -----------------------------
        # SESSION GATE
        # -----------------------------
        if market_session not in {"PRE", "REGULAR", "POST"}:
            return False

        # -----------------------------
        # TIME GATE
        # -----------------------------
        ts = now_ts if now_ts is not None else time.time()

        if self._state.last_observation_ts is None:
            return True

        elapsed = ts - self._state.last_observation_ts
        return elapsed >= self._min_cadence_seconds

    # --------------------------------------------------
    # STATE ADVANCEMENT (EXPLICIT)
    # --------------------------------------------------

    def mark_observation_proposed(
        self,
        *,
        now_ts: Optional[float] = None,
    ) -> None:
        """
        Record that an observation was proposed.

        This MUST be called only after an intent
        is successfully handed to LAW.
        """

        ts = now_ts if now_ts is not None else time.time()
        self._state.last_observation_ts = ts

"""
Observation Intent Proposers
SMC v1.0 — Formal Proposal Interfaces

This module defines the ONLY lawful ways ObservationIntent
objects may be proposed within ROGUE:OPS.

ROLE:
- Standardize intent creation
- Attribute requester identity
- Preserve auditability
- Prevent ad-hoc escalation

RULES:
- NO runtime behavior
- NO market access
- NO authorization
- NO execution
"""

from typing import Optional

from strategy.observation.types import (
    ObservationIntent,
    ObservationAction,
    ObservationScope,
)


# ==================================================
# BASE PROPOSER (DOCUMENTATION ONLY)
# ==================================================

class ObservationProposer:
    """
    Abstract role marker for observation proposers.

    This class exists for semantic clarity only.
    It is not meant to be instantiated.
    """

    requester: str


# ==================================================
# STRATEGY PROPOSER
# ==================================================

class StrategyObservationProposer(ObservationProposer):
    requester = "STRATEGY"

    @staticmethod
    def propose(
        *,
        action: ObservationAction,
        scope: ObservationScope,
        reason: str,
        cadence_hint_seconds: Optional[int] = None,
    ) -> ObservationIntent:
        """
        Propose an ObservationIntent on behalf of a strategy.
        """
        return ObservationIntent.create(
            requester="STRATEGY",
            action=action,
            scope=scope,
            cadence_hint_seconds=cadence_hint_seconds,
            reason=reason,
        )


# ==================================================
# AI PROPOSER (ADVISORY ONLY)
# ==================================================

class AIObservationProposer(ObservationProposer):
    requester = "AI"

    @staticmethod
    def propose(
        *,
        action: ObservationAction,
        scope: ObservationScope,
        reason: str,
        cadence_hint_seconds: Optional[int] = None,
    ) -> ObservationIntent:
        """
        Propose an ObservationIntent on behalf of an AI advisor.

        This does NOT imply permission.
        """
        return ObservationIntent.create(
            requester="AI",
            action=action,
            scope=scope,
            cadence_hint_seconds=cadence_hint_seconds,
            reason=reason,
        )


# ==================================================
# SYSTEM PROPOSER
# ==================================================

class SystemObservationProposer(ObservationProposer):
    requester = "SYSTEM"

    @staticmethod
    def propose(
        *,
        action: ObservationAction,
        scope: ObservationScope,
        reason: str,
        cadence_hint_seconds: Optional[int] = None,
    ) -> ObservationIntent:
        """
        Propose an ObservationIntent on behalf of system orchestration.
        """
        return ObservationIntent.create(
            requester="SYSTEM",
            action=action,
            scope=scope,
            cadence_hint_seconds=cadence_hint_seconds,
            reason=reason,
        )

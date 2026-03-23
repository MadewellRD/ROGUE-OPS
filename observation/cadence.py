"""
Observation Cadence Policy
SMC v1.0 — Deterministic Timing Authority

This module defines cadence enforcement logic for observation.

ROLE:
- Decide whether observation is permitted at a given moment
- Enforce cadence and safety rules
- Produce auditable, replay-safe decisions

RULES:
- NO sleeping
- NO looping
- NO threads
- NO vendor access
- Pure decision logic only
"""

from dataclasses import dataclass
from typing import Optional
import datetime as dt


# ==================================================
# CADENCE DECISION STRUCT
# ==================================================

@dataclass(frozen=True)
class CadenceDecision:
    """
    Result of cadence evaluation.
    """

    allow: bool
    reason: str
    seconds_until_next_allowed: Optional[int]


# ==================================================
# CADENCE EVALUATION
# ==================================================

def evaluate_cadence(
    *,
    now_utc: dt.datetime,
    last_observation_ts: Optional[dt.datetime],
    cadence_seconds: Optional[int],
    kill_active: bool,
) -> CadenceDecision:
    """
    Evaluate whether observation is allowed at this moment.

    All inputs are explicit to preserve replay safety.
    """

    # ----------------------------------------------
    # HARD DENY — SYSTEM KILL
    # ----------------------------------------------
    if kill_active:
        return CadenceDecision(
            allow=False,
            reason="Kill switch active",
            seconds_until_next_allowed=None,
        )

    # ----------------------------------------------
    # DENY — NO CADENCE DEFINED
    # ----------------------------------------------
    if cadence_seconds is None:
        return CadenceDecision(
            allow=False,
            reason="No cadence defined",
            seconds_until_next_allowed=None,
        )

    # ----------------------------------------------
    # ALLOW — FIRST OBSERVATION
    # ----------------------------------------------
    if last_observation_ts is None:
        return CadenceDecision(
            allow=True,
            reason="First observation permitted",
            seconds_until_next_allowed=0,
        )

    # ----------------------------------------------
    # ELAPSED TIME CHECK
    # ----------------------------------------------
    elapsed = (now_utc - last_observation_ts).total_seconds()

    if elapsed >= cadence_seconds:
        return CadenceDecision(
            allow=True,
            reason="Cadence elapsed",
            seconds_until_next_allowed=0,
        )

    # ----------------------------------------------
    # DENY — TOO SOON
    # ----------------------------------------------
    remaining = int(cadence_seconds - elapsed)

    return CadenceDecision(
        allow=False,
        reason="Cadence not yet elapsed",
        seconds_until_next_allowed=max(remaining, 1),
    )

"""
Arbitration Types
SMC v1.0 — Canonical, Pure Data Contracts

This module defines the immutable data structures used
by the arbitration layer.

RULES:
- NO runtime logic
- NO imports from arbitration.engine
- NO side effects
"""

from dataclasses import dataclass
from typing import List, Optional, Literal


# ==================================================
# STRATEGY → ARBITRATION INPUT
# ==================================================

@dataclass(frozen=True)
class StrategyIntent:
    """
    Non-authoritative intent proposed by a single strategy.
    """

    strategy_id: str
    symbol: str
    structure: str
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    horizon: str
    risk_class: str
    confidence: float
    snapshot_id: str


# ==================================================
# MERGED (PORTFOLIO-LEVEL) INTENT
# ==================================================

@dataclass(frozen=True)
class MergedIntent:
    """
    Portfolio-level intent composed of one or more StrategyIntents.
    """

    symbol: str
    structure: str
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    horizon: str
    risk_class: str
    contributing_strategies: List[str]
    snapshot_id: str


# ==================================================
# ARBITRATION → LAW / FEEDBACK OUTPUT (CANONICAL)
# ==================================================

@dataclass(frozen=True)
class ArbitrationDecision:
    """
    Canonical arbitration output.

    This object represents the FINAL, non-executing decision
    of the arbitration layer and is evaluated by the LAW stack.

    It does NOT authorize execution.
    It proposes a disposition.
    """

    symbol: str
    directive: Literal[
        "ENTRY_CANDIDATE",
        "EXIT_REQUIRED",
        "HOLD",
        "FLAT",
        "REJECTED",
    ]

    merged_intent: Optional[MergedIntent]

    violated_laws: List[str]
    notes: Optional[str]
    snapshot_id: str

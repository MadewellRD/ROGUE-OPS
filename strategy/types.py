"""
Strategy Types
SMC v1.1 — StrategyContext Confidence Extension

NOTE:
- SEE depends on this file
- Changes are additive only
- No authority, logic, or mutation is allowed here
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any


# ==================================================
# INDICATOR STATE (READ-ONLY, ADVISORY)
# ==================================================

@dataclass(frozen=True)
class IndicatorState:
    """
    Read-only indicator summary exposed to StrategyModules.

    - Derived from IndicatorAuthority
    - Snapshot-scoped
    - Deterministic
    - Advisory only
    """

    values: Dict[str, float]
    regime: Optional[str] = None


# ==================================================
# STRATEGY CONTEXT (v1.1)
# ==================================================

@dataclass(frozen=True)
class StrategyContext:
    """
    Immutable context passed to all StrategyModules.

    v1.1 additions:
    - strategy_confidence
    - portfolio_pressure
    - capital_state
    """

    # ---- Evaluation Metadata ----
    evaluation_id: str
    snapshot_id: str

    # ---- Confidence & Portfolio Signals ----
    strategy_confidence: Dict[str, int]
    portfolio_pressure: str
    capital_state: str
    session: str

    # ---- Optional Extensions ----
    metadata: Optional[Dict[str, Any]] = None

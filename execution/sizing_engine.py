#
# sizing_engine.py
#
# Scaling & Position Sizing Engine
# PHASE 15 — ATOMIC (NO SUBPHASES)
#
# Responsible for:
# - Deterministic contract sizing
# - Confidence-based scaling (bounded)
# - Enforcing absolute size caps
#
# Explicitly NOT responsible for:
# - Trade approval
# - Risk enforcement
# - Option selection
# - Execution
#

from dataclasses import dataclass
from typing import Optional

from execution. execution_contracts import ExecutionIntent
from market.market_data import MarketSnapshot


# ----------------------------
# Hard caps (institutional)
# ----------------------------

BASE_CONTRACT_SIZE = 1
MAX_CONTRACTS = 5


# ----------------------------
# Sizing context
# ----------------------------

@dataclass(frozen=True)
class SizingContext:
    """
    Optional external confidence input.

    confidence:
        - None      → baseline size
        - 1..N      → linear multiplier
    """
    confidence: Optional[int] = None


# ----------------------------
# Sizing Engine
# ----------------------------

class SizingEngine:
    """
    Deterministic position sizing authority.
    """

    def determine_quantity(
        self,
        *,
        intent: ExecutionIntent,
        snapshot: MarketSnapshot,
        context: SizingContext = SizingContext(),
    ) -> int:
        """
        Determine contract quantity.

        Returns:
            Integer contract count.
        """

        # ----------------------------
        # Baseline
        # ----------------------------
        qty = BASE_CONTRACT_SIZE

        # ----------------------------
        # Confidence scaling (bounded)
        # ----------------------------
        if context.confidence is not None:
            if context.confidence <= 0:
                raise RuntimeError("Confidence must be positive")

            qty *= context.confidence

        # ----------------------------
        # Absolute cap enforcement
        # ----------------------------
        if qty > MAX_CONTRACTS:
            qty = MAX_CONTRACTS

        return qty

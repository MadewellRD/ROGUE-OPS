#
# option_selector.py
#
# Option Selection Engine
# PHASE 9 — ATOMIC (LOCKED)
#
# Responsible for:
# - Selecting a REAL option contract from IBKR-discovered candidates
# - Deterministic ATM-first strike preference using MarketSnapshot
# - Producing a fully-specified ExecutionIntent.option()
#
# Explicitly NOT responsible for:
# - Market data fetching
# - Option qualification
# - Risk sizing or limits
# - Execution or broker logic
# - OPS state
#

from typing import Literal, List

from execution_contracts import ExecutionIntent
from option_qualifier import QualifiedOption
from ibkr_option_discovery import DiscoveredOption
from market_data import MarketSnapshot


# ----------------------------
# Type constraints
# ----------------------------

DirectionType = Literal["CALL", "PUT"]


# ----------------------------
# Helpers
# ----------------------------

def _select_atm_contract(
    *,
    discovered: List[DiscoveredOption],
    spot: float,
) -> DiscoveredOption:
    """
    Deterministic ATM-first contract selection.

    Rules:
    - Choose strike closest to spot
    - Deterministic tie-break: lower strike wins
    """

    if not discovered:
        raise RuntimeError("No discovered contracts provided")

    return min(
        discovered,
        key=lambda c: (abs(c.strike - spot), c.strike),
    )


# ----------------------------
# Public API
# ----------------------------

def select_0dte_option(
    *,
    qualified: QualifiedOption,
    discovered: List[DiscoveredOption],
    snapshot: MarketSnapshot,
    direction: DirectionType,
    strategy_tag: str,
    quantity: int = 1,
) -> ExecutionIntent:
    """
    Convert IBKR-discovered contracts into a concrete ExecutionIntent.

    Deterministic.
    Replay-safe.
    Broker-backed.

    Inputs:
        qualified   : Phase 8 QualifiedOption (structural validation only)
        discovered  : Phase 9A DiscoveredOption list
        snapshot    : Phase 10 MarketSnapshot (SOLE price authority)
        direction   : CALL or PUT
        strategy_tag: Strategy attribution
        quantity    : Contract count (default 1)

    Returns:
        ExecutionIntent.option()
    """

    # ----------------------------
    # Direction enforcement
    # ----------------------------
    if direction == "CALL":
        right = "C"
        action = "BUY"
    elif direction == "PUT":
        right = "P"
        action = "BUY"
    else:
        raise ValueError("Direction must be CALL or PUT")

    # ----------------------------
    # Authority checks
    # ----------------------------
    if snapshot.symbol != qualified.symbol:
        raise RuntimeError("MarketSnapshot symbol mismatch")

    # ----------------------------
    # Filter discovered contracts
    # ----------------------------
    candidates = [
        c for c in discovered
        if c.symbol == qualified.symbol
        and c.expiry == qualified.expiry
        and c.right == right
    ]

    if not candidates:
        raise RuntimeError("No matching discovered contracts after filtering")

    # ----------------------------
    # Deterministic ATM selection
    # ----------------------------
    chosen = _select_atm_contract(
        discovered=candidates,
        spot=snapshot.spot,
    )

    # ----------------------------
    # Construct canonical intent
    # ----------------------------
    return ExecutionIntent.option(
        symbol=chosen.symbol,
        qty=quantity,
        action=action,
        expiry=chosen.expiry,
        strike=chosen.strike,
        right=chosen.right,
        tag=strategy_tag,
    )

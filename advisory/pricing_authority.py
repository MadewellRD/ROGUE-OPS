#
# execution_driver.py
#
# Execution Driver
# PHASE 15 — WIRING AUTHORITY
# PHASE 16 — PRICING AUTHORITY INTEGRATION (ADD ONLY)
#
# Responsible for:
# - Executing authorized envelopes
# - Obtaining canonical execution price (Phase 16)
# - Delegating position mutation to Phase 15
#
# Explicitly NOT responsible for:
# - Strategy
# - Risk
# - Market data fetching
#

from execution_router import execute
from execution_position_bridge import ExecutionPositionBridge
from execution_envelope import ExecutionEnvelope
from state_machine import StateMachineV2
from market_data import MarketSnapshot
from pricing_authority import PricingAuthority


def execute_and_apply(
    *,
    envelope: ExecutionEnvelope,
    snapshot: MarketSnapshot,
    state_machine: StateMachineV2,
    account_id: str,
):
    """
    Canonical execution + pricing + position mutation path.

    This is the ONLY approved live/PAPER execution entrypoint.
    """

    # ----------------------------
    # Phase 16 — Pricing Authority
    # ----------------------------
    pricing = PricingAuthority()
    entry_price = pricing.determine_entry_price(
        envelope=envelope,
        snapshot=snapshot,
    )

    # ----------------------------
    # Phase 3 — Execution
    # ----------------------------
    result = execute(envelope, account_id)

    # ----------------------------
    # Phase 15 — Position mutation
    # ----------------------------
    bridge = ExecutionPositionBridge(
        state_machine=state_machine
    )
    bridge.handle_entry(
        envelope=envelope,
        result=result,
        entry_price=entry_price,
    )

    return result

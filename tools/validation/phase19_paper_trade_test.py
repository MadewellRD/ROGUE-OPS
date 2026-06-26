#
# phase19_paper_trade_test.py
#
# Phase 19 — Authoritative PAPER Trade Test
# ATOMIC (TEST-ONLY, REMOVABLE)
#
# PURPOSE:
# - Prove end-to-end LIVE/PAPER execution
# - Exercise the full OPS path:
#
#   MarketSnapshot
#        ↓
#   IntentAuthority
#        ↓
#   RiskEngine
#        ↓
#   ExecutionEnvelope
#        ↓
#   ExecutionRouter (PAPER → IBKR)
#        ↓
#   Position mutation
#
# HARD RULES:
# - NO monkey patches
# - NO forced shortcuts
# - NO bypass of IntentAuthority
# - NO replay logic
#

import os
import datetime as dt

from market_data import create_market_snapshot
from intent_authority import IntentAuthority
from state_machine import StateMachineV2, SystemState
from execution_envelope import ExecutionEnvelope
from execution_driver import execute_and_apply
from position_store import get_position_store


def main():
    print("\n=== PHASE 19 PAPER TRADE TEST START ===\n")

    # --------------------------------------------------
    # HARD ENVIRONMENT ASSERTIONS
    # --------------------------------------------------
    assert os.getenv("OPS_MODE") == "PAPER", "OPS_MODE must be PAPER"
    assert os.getenv("EXECUTION_MODE") == "PAPER", "EXECUTION_MODE must be PAPER"
    assert os.getenv("OPS_ENV") == "PROD", "OPS_ENV must be PROD"
    assert os.getenv("OPS_KILL_SWITCH", "false") == "false", "Kill switch must be OFF"

    account_id = os.getenv("IBKR_ACCOUNT_ID")
    if not account_id:
        raise RuntimeError("IBKR_ACCOUNT_ID not set")

    print("[OK] Environment validated for PAPER execution")

    # --------------------------------------------------
    # CLEAN POSITION STATE
    # --------------------------------------------------
    store = get_position_store()
    if store.has_open_position():
        raise RuntimeError("Refusing to run with an open position")

    # --------------------------------------------------
    # AUTHORITIES
    # --------------------------------------------------
    sm = StateMachineV2(ibkr_account_id=account_id)
    intent_authority = IntentAuthority()

    # --------------------------------------------------
    # SYNTHETIC *LIVE-LIKE* MARKET SNAPSHOT
    # --------------------------------------------------
    now = dt.datetime(
	year=2026,
	month=1,
	day=14,
	hour=14,
	minute=35,
	second=9,
)

    snapshot = create_market_snapshot(
        symbol="SPY",
        spot=round(700.0, 2),          # Explicit asserted spot
        timestamp_utc=now,
        session="REGULAR",
        source="PAPER",
    )

    print(f"[SNAPSHOT] {snapshot}")

    # --------------------------------------------------
    # PHASE 13 — INTENT AUTHORITY
    # --------------------------------------------------
    intent = intent_authority.evaluate(snapshot)

    if intent is None:
        raise RuntimeError("IntentAuthority did not emit an intent")

    print(f"[INTENT] {intent.intent_id} {intent.symbol} {intent.option}")

    # --------------------------------------------------
    # PHASE 14 — AUTHORIZE ENTRY (RISK + OPS)
    # --------------------------------------------------
    sm.authorize_entry(
        intent=intent,
        snapshot=snapshot,
    )

    if sm.state != SystemState.OPEN_POSITION:
        raise RuntimeError("State machine did not enter OPEN_POSITION")

    # --------------------------------------------------
    # PHASE 15 — EXECUTION + POSITION MUTATION
    # --------------------------------------------------
    envelope = ExecutionEnvelope.create(
        intent=intent,
        ops_state=sm.ops.get(),
        risk_ok=True,
        authorized=True,
    )

    result = execute_and_apply(
        envelope=envelope,
        state_machine=sm,
        account_id=account_id,
        entry_price=1.00,  # Explicit test price (broker fills will differ)
    )

    print(f"[EXECUTION RESULT] {result.status} order_id={result.order_id}")

    # --------------------------------------------------
    # ASSERT POSITION OPEN
    # --------------------------------------------------
    if not store.has_open_position():
        raise RuntimeError("Position was not opened")

    position = store.get_open_position()
    print(f"[POSITION OPENED] {position}")

    print("\n=== PHASE 19 PAPER TRADE TEST COMPLETE ===\n")
    print("→ Check TWS / IBKR Paper account for live option order")


if __name__ == "__main__":
    main()

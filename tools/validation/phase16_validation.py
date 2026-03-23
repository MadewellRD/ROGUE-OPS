#
# phase16_validation.py
#
# Phase 16 Validation Harness
#
# Validates:
# - Entry price authority
# - ExecutionDriver wiring
# - Position mutation correctness
#
# Broker-free
# Deterministic
# Replay-only
#

import datetime as dt

from market_data import create_market_snapshot
from execution_envelope import ExecutionEnvelope
from execution_contracts import ExecutionIntent
from execution_driver import execute_and_apply
from state_machine import StateMachineV2, SystemState
from ops_state import get_ops_state
from position_store import get_position_store


def main():
    print("\n=== PHASE 16 VALIDATION START ===\n")

    # ----------------------------
    # Reset global state
    # ----------------------------
    store = get_position_store()
    if store.has_open_position():
        store.close_position()

    ops = get_ops_state()
    ops.clear()

    sm = StateMachineV2(ibkr_account_id="REPLAY")

    # ----------------------------
    # Canonical Market Snapshot (Phase 10)
    # ----------------------------
    snapshot = create_market_snapshot(
        symbol="SPY",
        spot=700.0,
        timestamp_utc=dt.datetime(2026, 1, 13, 14, 35),
        session="REGULAR",
        source="REPLAY",
    )

    # ----------------------------
    # Canonical Intent (Phase 13)
    # ----------------------------
    intent = ExecutionIntent.option(
        symbol="SPY",
        qty=1,
        action="BUY",
        expiry="20260113",
        strike=700,
        right="C",
        tag="PHASE_16_TEST",
    )

    # ----------------------------
    # Authorize entry (Phase 14)
    # ----------------------------
    sm.authorize_entry(
        intent=intent,
        snapshot=snapshot,
    )

    # ----------------------------
    # Envelope creation (Phase 2)
    # ----------------------------
    envelope = ExecutionEnvelope.create(
        intent=intent,
        ops_state=ops.get(),
        risk_ok=True,
        authorized=True,
    )

    # ----------------------------
    # Entry price authority (Phase 16)
    # ----------------------------
    entry_price = 1.23  # deterministic, explicit

    # ----------------------------
    # Execute + apply (Phase 15)
    # ----------------------------
    result = execute_and_apply(
        envelope=envelope,
        state_machine=sm,
        account_id="REPLAY",
        entry_price=entry_price,
    )

    # ----------------------------
    # Assertions
    # ----------------------------
    print("\n=== PHASE 16 ASSERTIONS ===")

    if not store.has_open_position():
        print("[FAIL] No position opened")
        return

    pos = store.get_open_position()

    if pos.entry_price != entry_price:
        print("[FAIL] Entry price mismatch")
        return

    if sm.state != SystemState.MANAGING_POSITION:
        print("[FAIL] State machine not in MANAGING_POSITION")
        return

    print("[PASS] Phase 16 validated successfully")
    print(f"       Entry Price: {pos.entry_price}")
    print(f"       Position ID: {pos.position_id}")

    print("\n=== PHASE 16 VALIDATION COMPLETE ===\n")


if __name__ == "__main__":
    main()

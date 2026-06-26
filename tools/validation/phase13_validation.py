#
# phase13_validation.py
#
# Phase 13 Validation Harness
#
# Broker-free, deterministic, replay-only test
#

import datetime as dt

from market_data import create_market_snapshot
from state_machine import StateMachineV2, SystemState
from intent_authority import IntentAuthority
from replay_engine import ReplayEngine
from position_store import get_position_store
from position import Position


def synthetic_snapshots():
    base_date = dt.date(2026, 1, 13)

    times = [
        dt.time(14, 0),   # before entry window
        dt.time(14, 35),  # entry window → EXPECT ENTRY
        dt.time(14, 45),  # holding position
        dt.time(20, 56),  # hard exit → EXPECT EXIT
    ]

    for t in times:
        yield create_market_snapshot(
            symbol="SPY",
            spot=700.0,
            timestamp_utc=dt.datetime.combine(base_date, t),
            session="REGULAR",
            source="REPLAY",
        )


def main():
    print("\n=== PHASE 13 VALIDATION START ===\n")

    store = get_position_store()
    if store.has_open_position():
        store.close_position()

    sm = StateMachineV2(ibkr_account_id="REPLAY")
    intent_authority = IntentAuthority()

    engine = ReplayEngine(
        state_machine=sm,
        intent_authority=intent_authority,
    )

    # --------------------------------------------------
    # Fake broker ENTRY confirmation
    # --------------------------------------------------

    def fake_open_position(intent):
        position = Position(
            position_id="TEST_POS_1",
            symbol=intent.symbol,
            sec_type="OPT",
            expiry=intent.option.expiry,
            strike=intent.option.strike,
            right=intent.option.right,
            action=intent.action,
            quantity=intent.quantity,
            entry_price=1.00,
            intent_id=intent.intent_id,
            envelope_hash="TEST_HASH",
            opened_at_utc=dt.datetime.now(dt.timezone.utc),
        )
        store.open_position(position)
        sm.on_position_opened()

    # --------------------------------------------------
    # Fake broker EXIT confirmation
    # --------------------------------------------------

    def fake_close_position():
        store.close_position()
        sm.on_position_closed()
        sm.on_audit_complete()

    # --------------------------------------------------
    # Patch authorize_entry
    # --------------------------------------------------

    original_authorize = sm.authorize_entry

    def wrapped_authorize(*, intent, snapshot):
        original_authorize(intent=intent, snapshot=snapshot)
        fake_open_position(intent)

    sm.authorize_entry = wrapped_authorize

    # --------------------------------------------------
    # Patch manage_position to consummate exit
    # --------------------------------------------------

    original_manage = sm.manage_position

    def wrapped_manage(*, snapshot):
        directive = original_manage(snapshot=snapshot)
        if directive is not None:
            fake_close_position()
        return directive

    sm.manage_position = wrapped_manage

    # --------------------------------------------------
    # Run replay
    # --------------------------------------------------

    engine.run(synthetic_snapshots())

    # --------------------------------------------------
    # Assertions
    # --------------------------------------------------

    print("\n=== PHASE 13 ASSERTIONS ===")

    if sm.state == SystemState.IDLE and not store.has_open_position():
        print("[PASS] Lifecycle completed and system returned to IDLE")
    else:
        print("[FAIL] System did not return to IDLE")
        print(f"State: {sm.state}")
        print(f"Open position: {store.has_open_position()}")

    print("\n=== PHASE 13 VALIDATION COMPLETE ===\n")


if __name__ == "__main__":
    main()

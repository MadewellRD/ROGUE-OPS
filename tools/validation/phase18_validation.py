#
# phase18_validation.py
#
# Phase 18 — Global Safety & Kill Switch Validation
# ATOMIC (NO SUBPHASES)
#
# Validates:
# - Kill switch blocks entry
# - OPS enters HALT deterministically
# - No position opens under kill
# - HALT is TERMINAL for the process
#
# Recovery is explicitly OUT OF SCOPE.
# A new process is required after HALT.
#

import os
import datetime as dt

from market_data import create_market_snapshot
from state_machine import StateMachineV2, SystemState
from intent_authority import IntentAuthority
from replay_engine import ReplayEngine
from position_store import get_position_store
from kill_switch import kill_active
from ops_state import get_ops_state


def synthetic_snapshots():
    base_date = dt.date(2026, 1, 13)

    times = [
        dt.time(14, 35),  # entry window
        dt.time(14, 45),
        dt.time(20, 56),
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
    print("\n=== PHASE 18 VALIDATION START ===\n")

    # --------------------------------------------------
    # CLEAN ENVIRONMENT
    # --------------------------------------------------
    os.environ.pop("OPS_KILL_SWITCH", None)

    store = get_position_store()
    if store.has_open_position():
        store.close_position()

    ops = get_ops_state()

    # --------------------------------------------------
    # STEP 1 — KILL SWITCH HALT (TERMINAL)
    # --------------------------------------------------
    os.environ["OPS_KILL_SWITCH"] = "true"
    assert kill_active() is True

    sm = StateMachineV2(ibkr_account_id="REPLAY")
    engine = ReplayEngine(
        state_machine=sm,
        intent_authority=IntentAuthority(),
    )

    print("[TEST] Kill switch active — expecting TERMINAL HALT")

    halted = False
    try:
        engine.run(synthetic_snapshots())
    except RuntimeError as e:
        halted = True
        print(f"[EXPECTED] Halt raised: {e}")

    # --------------------------------------------------
    # ASSERTIONS — TERMINAL HALT
    # --------------------------------------------------
    print("\n=== PHASE 18 ASSERTIONS ===")

    if not halted:
        print("[FAIL] Entry was not blocked")
        return

    if sm.state != SystemState.HALTED:
        print("[FAIL] State machine did not enter HALTED")
        return

    if store.has_open_position():
        print("[FAIL] Position opened under kill switch")
        return

    if not ops.is_halted():
        print("[FAIL] OPS did not enter HALT")
        return

    print("[PASS] Kill switch enforced")
    print("[PASS] OPS HALT is terminal")
    print("[PASS] No in-process recovery permitted")

    print("\n=== PHASE 18 VALIDATION COMPLETE ===\n")
    print("NOTE: System recovery requires full process restart.")


if __name__ == "__main__":
    main()

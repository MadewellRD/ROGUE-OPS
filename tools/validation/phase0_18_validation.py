#
# phase0_18_validation.py
#
# Phase 0–18 FULL SYSTEM VALIDATION HARNESS
# INSTITUTIONAL / DOCTRINE-COMPLIANT
#

import os
import datetime as dt

from execution_contracts import ExecutionIntent
from execution_envelope import ExecutionEnvelope
from execution_router import execute
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
        dt.time(14, 0),
        dt.time(14, 35),
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
    print("\n=== PHASE 0–18 FULL VALIDATION START ===\n")

    # --------------------------------------------------
    # CLEAN START (REQUIRED)
    # --------------------------------------------------
    os.environ.pop("OPS_KILL_SWITCH", None)

    ops = get_ops_state()
    if ops.is_halted():
        raise RuntimeError(
            "OPS is HALTED at harness start — restart process required"
        )

    store = get_position_store()
    if store.has_open_position():
        store.close_position()

    # --------------------------------------------------
    # PHASE 0–3 — INTENT → ENVELOPE → EXECUTION
    # --------------------------------------------------
    print("[CHECK] Phase 0–3: Intent → Envelope → Execution")

    intent = ExecutionIntent.option(
        symbol="SPY",
        qty=1,
        action="BUY",
        expiry="20260113",
        strike=700,
        right="C",
        tag="PHASE_0_3_TEST",
    )

    envelope = ExecutionEnvelope.create(
        intent=intent,
        ops_state=ops.get(),
        risk_ok=True,
        authorized=True,
    )

    result = execute(envelope, account_id="SIM")
    assert result.status == "SUBMITTED"

    print("[PASS] Phase 0–3")

    # --------------------------------------------------
    # PHASE 10–17 — FULL LIFECYCLE
    # --------------------------------------------------
    print("[CHECK] Phase 10–17: Market → Intent → Position → Exit")

    sm = StateMachineV2(ibkr_account_id="REPLAY")
    engine = ReplayEngine(
        state_machine=sm,
        intent_authority=IntentAuthority(),
    )

    engine.run(synthetic_snapshots())

    assert sm.state == SystemState.IDLE
    assert not store.has_open_position()

    print("[PASS] Phase 10–17")

    # --------------------------------------------------
    # PHASE 18 — TERMINAL KILL SWITCH (FINAL)
    # --------------------------------------------------
    print("[CHECK] Phase 18: Global Kill Switch (Terminal)")

    os.environ["OPS_KILL_SWITCH"] = "true"
    assert kill_active() is True

    sm = StateMachineV2(ibkr_account_id="REPLAY")
    engine = ReplayEngine(
        state_machine=sm,
        intent_authority=IntentAuthority(),
    )

    halted = False
    try:
        engine.run(synthetic_snapshots())
    except RuntimeError:
        halted = True

    assert halted
    assert sm.state == SystemState.HALTED
    assert ops.is_halted()
    assert not store.has_open_position()

    print("[PASS] Phase 18")

    # --------------------------------------------------
    # END — NO RECOVERY ALLOWED
    # --------------------------------------------------
    print("\n=== FINAL RESULT ===")
    print("[PASS] Phase 0–18 VALIDATION COMPLETE")
    print("[PASS] OPS CORE IS LOCKED & INSTITUTIONAL")
    print("[INFO] Process must now terminate")
    print("\n=== END ===\n")


if __name__ == "__main__":
    main()

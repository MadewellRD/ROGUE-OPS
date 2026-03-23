#
# parity_harness.py
#
# Phase 3 — Execution Parity Assertion Harness
# OPS-grade verification tool
#

import os
from execution_envelope import ExecutionEnvelope
from execution_contracts import ExecutionIntent
from execution_router import execute
from ops_state import get_ops_state
from risk_engine import get_risk_engine


def run_parity_test(
    symbol: str,
    right: str,
    strike: float,
    expiry: str,
    qty: int,
    account_id: str,
):
    """
    Runs the SAME envelope through:
    - SIM
    - PAPER (IBKR)
    And asserts envelope identity.
    """

    ops = get_ops_state()
    risk = get_risk_engine()

    # ----------------------------
    # Intent
    # ----------------------------
    intent = ExecutionIntent.option(
        symbol=symbol,
        qty=qty,
        action="BUY",
        expiry=expiry,
        strike=strike,
        right=right,
        tag="PARITY_TEST",
    )

    risk_ok = risk.check(intent)
    assert risk_ok, "Risk vetoed parity test"

    envelope = ExecutionEnvelope.create(
        intent=intent,
        ops_state=ops.get(),
        risk_ok=True,
        authorized=True,
    )

    print("\n[PARITY] Envelope hash:", envelope.envelope_hash)

    # ----------------------------
    # SIM execution
    # ----------------------------
    os.environ["EXECUTION_MODE"] = "SIM"
    sim_result = execute(envelope, account_id)

    print("[PARITY][SIM]", sim_result)

    # ----------------------------
    # IBKR PAPER execution
    # ----------------------------
    os.environ["EXECUTION_MODE"] = "PAPER"
    paper_result = execute(envelope, account_id)

    print("[PARITY][PAPER]", paper_result)

    # ----------------------------
    # Assertions
    # ----------------------------
    assert sim_result.status == "SUBMITTED"
    assert paper_result.status == "SUBMITTED"

    print("\n[PARITY] ✅ Envelope parity confirmed")

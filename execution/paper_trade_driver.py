#
# paper_trade_driver.py
#
# Paper Trade Driver
# PHASE 32 — ONE-BUTTON INVESTOR DEMO
# PHASE 50 — PAPER DETERMINISM BASELINE
#
# Purpose:
# - End-to-end validation of:
#   MarketSnapshot → Indicators → SignalEngine
#   → Intent → Risk → Envelope → SIZED Execution → Audit
#
# PAPER MODE ONLY
#

import os
from typing import Any

from governance.gcp_clients import get_api_keys
from execution.state_machine import StateMachineV2
from execution.execution_router import execute_sized
from market.market_data_adapter_steady import get_market_snapshot
from advisory.signal_engine import SignalEngine
from governance.api_clients import fetch_and_aggregate_indicators
from advisory.indicator_authority import IndicatorAssertion
from governance.kill_switch import kill_active


# ==================================================
# HARD ASSERTIONS (PROCESS LEVEL)
# ==================================================

EXECUTION_MODE = os.getenv("EXECUTION_MODE")
OPS_MODE = os.getenv("OPS_MODE")
IBKR_ACCOUNT_ID = os.getenv("IBKR_ACCOUNT_ID")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

if EXECUTION_MODE != "PAPER":
    raise RuntimeError("paper_trade_driver may ONLY run in PAPER mode")

if OPS_MODE != "PAPER":
    raise RuntimeError("OPS_MODE must be PAPER for paper_trade_driver")

if not IBKR_ACCOUNT_ID:
    raise RuntimeError("IBKR_ACCOUNT_ID not set")

if not GCP_PROJECT_ID:
    raise RuntimeError("GCP_PROJECT_ID not set")


# ==================================================
# PRETTY PRINT HELPERS (READ-ONLY)
# ==================================================

def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def pretty_print_market_snapshot(snapshot) -> None:
    print("\n[MARKET SNAPSHOT]")
    print(f"  SYMBOL  : {snapshot.symbol}")
    print(f"  PRICE   : {snapshot.spot:.2f}")
    print(f"  SESSION : {snapshot.session}")
    print(f"  TIME    : {snapshot.timestamp_utc.isoformat()}")
    print(f"  SOURCE  : {snapshot.source}")


def pretty_print_indicator_assertion(assertion: IndicatorAssertion) -> None:
    print("\n[INDICATOR ASSERTION — PHASE 28]")
    print("  REQUIRED:")
    for k in sorted(assertion.required.keys()):
        print(f"    - {k:<22}: {_fmt(assertion.required[k])}")

    if assertion.advisory:
        print("\n  ADVISORY (NON-AUTHORITATIVE):")
        for k in sorted(assertion.advisory.keys()):
            print(f"    - {k:<22}: {_fmt(assertion.advisory[k])}")

    print(f"\n  ASSERTION HASH : {assertion.assertion_hash}")


# ==================================================
# MAIN
# ==================================================

def main() -> None:
    print("\n--- PAPER TRADE DRIVER START (PHASE 32 + PHASE 50) ---")

    # --------------------------------------------------
    # Retrieve API keys
    # --------------------------------------------------

    api_keys = get_api_keys(
        project_id=GCP_PROJECT_ID,
        secret_names=["steadyapi-key"],
    )

    steady_api_key = api_keys.get("steadyapi-key")
    if not steady_api_key:
        raise RuntimeError("STEADYAPI key missing from Secret Manager")

    # --------------------------------------------------
    # Kill switch
    # --------------------------------------------------

    if kill_active():
        raise RuntimeError("Kill switch active — aborting")

    # --------------------------------------------------
    # Initialize OPS State Machine
    # --------------------------------------------------

    sm = StateMachineV2(
        ibkr_account_id=IBKR_ACCOUNT_ID,
    )

    # --------------------------------------------------
    # Market Snapshot (LIVE PAPER DATA)
    # --------------------------------------------------

    snapshot = get_market_snapshot(
        symbol="SPY",
        source="PAPER",
        api_key=steady_api_key,
    )

    pretty_print_market_snapshot(snapshot)

    # --------------------------------------------------
    # Indicator Assertion (AUTHORITATIVE)
    # --------------------------------------------------

    indicator_assertion = fetch_and_aggregate_indicators(
        ticker=snapshot.symbol,
        api_key=steady_api_key,
    )

    if not isinstance(indicator_assertion, IndicatorAssertion):
        raise RuntimeError("Indicator authority violation: expected IndicatorAssertion")

    pretty_print_indicator_assertion(indicator_assertion)

    # --------------------------------------------------
    # SIGNAL EVALUATION (PHASE 28)
    # --------------------------------------------------

    signal_engine = SignalEngine()
    result = signal_engine.evaluate(
        snapshot=snapshot,
        indicators=indicator_assertion,
    )

    if result is None:
        print("\n[SIGNAL RESULT]")
        print("  STATUS : NO SIGNAL PERMITTED")
        print("  REASON : Phase 28 required conditions not fully aligned")
        print(f"  SYMBOL : {snapshot.symbol}")
        print(f"  TIME   : {snapshot.timestamp_utc.isoformat()}")
        print("\n--- PAPER TRADE DRIVER COMPLETE (NO TRADE) ---")
        return

    intent, signal_context = result

    print("\n[SIGNAL RESULT]")
    print("  STATUS : SIGNAL PERMITTED")
    print(f"  INTENT : {intent.intent_id}")
    print(f"  WHY    : {signal_context.context_hash}")

    # --------------------------------------------------
    # AUTHORIZE ENTRY
    # --------------------------------------------------

    envelope = sm.authorize_entry(
        intent=intent,
        snapshot=snapshot,
        execution_mode="PAPER",
    )

    print(f"\n[PAPER ENVELOPE] {envelope.envelope_hash}")

    # --------------------------------------------------
    # EXECUTE (SIZED, BALANCE-AWARE)
    # --------------------------------------------------

    result = execute_sized(
        envelope=envelope,
        account_id=IBKR_ACCOUNT_ID,
    )

    print("\n[PAPER RESULT]")
    print(f"  STATUS : {result.status}")
    print(f"  REASON : {result.reason}")

    print("\n--- PAPER TRADE DRIVER COMPLETE (PHASE 50) ---")


# ==================================================
# ENTRYPOINT
# ==================================================

if __name__ == "__main__":
    main()

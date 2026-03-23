#
# sim_trade_driver.py
#
# SIM Trade Driver — Deterministic Execution Path
# PHASE 48 — SIMULATION AUTHORITY
#
# Purpose:
# - Exercise full OPS execution path in SIM mode
# - Validate determinism, sizing, and parity
# - Require NO broker, NO credentials
#
# SIM ONLY • SAFE • NON-INTERACTIVE
#

import os
import datetime as dt

from execution.state_machine import StateMachineV2
from execution.execution_router import execute_sized
from market.market_data import MarketSnapshot
from advisory.signal_engine import SignalEngine
from advisory.indicator_authority import (
    IndicatorAssertion,
    create_indicator_assertion,
)
from governance.kill_switch import kill_active


# ==================================================
# HARD ASSERTIONS
# ==================================================

if os.getenv("EXECUTION_MODE") != "SIM":
    raise RuntimeError("sim_trade_driver may ONLY run in SIM mode")

if os.getenv("OPS_MODE") != "SIM":
    raise RuntimeError("OPS_MODE must be SIM for sim_trade_driver")


# ==================================================
# SIM MARKET SNAPSHOT (PHASE 28 COMPLIANT)
# ==================================================

def get_sim_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="SPY",
        spot=500.00,
        session="REGULAR",
        timestamp_utc=dt.datetime.now(dt.timezone.utc),
        source="SIM",
    )


# ==================================================
# SIM INDICATOR ASSERTION (PHASE 28 EXACT MATCH)
# ==================================================

def get_sim_indicator_assertion() -> IndicatorAssertion:
    required = {
        "VWAP_Position": "above",
        "EMA9_Position": "above",
        "EMA9_Slope": "up",
        "RSI(7)": 62.0,
        "MACD_Histogram": 0.30,
        "ATR": 1.25,
        "Volume_State": "expanding",
        "IWM_VWAP_Alignment": "aligned",
    }

    advisory = {
        "SIM_NOTE": "Deterministic Phase 28 pass",
    }

    return create_indicator_assertion(
        required=required,
        advisory=advisory,
    )


# ==================================================
# MAIN
# ==================================================

def main() -> None:
    print("\n--- SIM TRADE DRIVER START (PHASE 48) ---")

    if kill_active():
        raise RuntimeError("Kill switch active — aborting")

    # --------------------------------------------------
    # OPS State Machine
    # --------------------------------------------------

    sm = StateMachineV2(
        ibkr_account_id="SIM",
    )

    # --------------------------------------------------
    # Market Snapshot
    # --------------------------------------------------

    snapshot = get_sim_snapshot()

    # --------------------------------------------------
    # Indicator Assertion
    # --------------------------------------------------

    indicators = get_sim_indicator_assertion()

    # --------------------------------------------------
    # Signal Evaluation
    # --------------------------------------------------

    signal_engine = SignalEngine()
    result = signal_engine.evaluate(
        snapshot=snapshot,
        indicators=indicators,
    )

    if result is None:
        raise RuntimeError("SIM driver expected SIGNAL, got NONE")

    intent, signal_context = result

    print(f"[SIM SIGNAL] INTENT={intent.intent_id}")
    print(f"[ASSERTION HASH] {indicators.assertion_hash}")

    # --------------------------------------------------
    # Authorize ENTRY
    # --------------------------------------------------

    envelope = sm.authorize_entry(
        intent=intent,
        snapshot=snapshot,
        execution_mode="SIM",
    )

    print(f"[SIM ENVELOPE] {envelope.envelope_hash}")

    # --------------------------------------------------
    # Execute (SIZED, SIM ORACLE)
    # --------------------------------------------------

    result = execute_sized(
        envelope=envelope,
        account_id="SIM",
    )

    print(f"[SIM RESULT] {result.status}")
    print(f"[PARITY HASH] {result.parity_hash}")

    print("\n--- SIM TRADE DRIVER COMPLETE ---")


# ==================================================
# ENTRYPOINT
# ==================================================

if __name__ == "__main__":
    main()

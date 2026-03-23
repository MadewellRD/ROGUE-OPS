#
# replay_driver.py
#
# Replay Driver — Parity Certification Harness
# PHASE 23 — REPLAY → LIVE PARITY (ATOMIC)
#
# Purpose:
# - Drive the live OPS stack using historical MarketSnapshots
# - Prove replay == live execution parity
# - Exercise SignalEngine, Risk, Envelope, Execution, Exit
# - Produce audit records identical in structure to PAPER / LIVE
#
# This file is:
# - Deterministic
# - Non-interactive
# - No strategy shortcuts
# - No replay-only logic
#

import os
from typing import Iterable

from state_machine import StateMachineV2
from execution_router import execute
from market_data import MarketSnapshot
from signal_engine import SignalEngine
from kill_switch import kill_active, engage_kill
from audit_store import get_audit_store


# ==================================================
# HARD ASSERTIONS
# ==================================================

EXECUTION_MODE = os.getenv("EXECUTION_MODE")

if EXECUTION_MODE != "REPLAY":
    raise RuntimeError("replay_driver may ONLY run in REPLAY mode")


# ==================================================
# REPLAY DRIVER
# ==================================================

class ReplayDriver:
    """
    Authoritative replay driver.

    This driver proves that historical market data
    can flow through the SAME OPS pipeline as live.
    """

    def __init__(
        self,
        *,
        snapshots: Iterable[MarketSnapshot],
        ibkr_account_id: str,
    ):
        self.snapshots = snapshots
        self.audit = get_audit_store()

        self.state_machine = StateMachineV2(
            ibkr_account_id=ibkr_account_id,
        )

        self.signal_engine = SignalEngine()

    # --------------------------------------------------
    # Run replay
    # --------------------------------------------------

    def run(self) -> None:
        """
        Execute deterministic replay.

        No branching.
        No fast paths.
        Same flow as live.
        """

        for snapshot in self.snapshots:

            if kill_active():
                engage_kill(reason="KILL_DURING_REPLAY")
                break

            # ----------------------------
            # Signal evaluation
            # ----------------------------
            intent = self.signal_engine.evaluate(
                snapshot=snapshot,
                indicators={},  # indicators must be pre-attached in snapshot pipeline
            )

            if intent is not None:
                envelope = self.state_machine.authorize_entry(
                    intent=intent,
                    snapshot=snapshot,
                    execution_mode="REPLAY",
                )

                result = execute(
                    envelope=envelope,
                    account_id=self.state_machine.ibkr_account_id,
                )

            # ----------------------------
            # Position management / exit
            # ----------------------------
            if self.state_machine.state.name == "MANAGING_POSITION":
                exit_envelope = self.state_machine.manage_position(
                    snapshot=snapshot,
                    execution_mode="REPLAY",
                )

                if exit_envelope is not None:
                    execute(
                        envelope=exit_envelope,
                        account_id=self.state_machine.ibkr_account_id,
                    )

        # --------------------------------------------------
        # Replay complete
        # --------------------------------------------------
        print("\n--- REPLAY COMPLETE ---")
        print(f"[AUDIT RECORDS] {len(self.audit.all_records())}")


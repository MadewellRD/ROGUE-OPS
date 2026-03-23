#
# deterministic_runner.py
#
# Deterministic Execution Runner
# PHASE 29 — BACKTEST / REPLAY / LIVE PARITY ENGINE (FINAL)
#
# This module is the SINGLE authoritative execution loop
# for:
#   - Replay
#   - Backtests
#   - Paper validation
#   - Investor demos
#
# Guarantees:
# - Snapshot-driven determinism
# - Replay == Paper == Capital parity
# - Full lifecycle execution
# - Audit completeness
#
# This module owns the LOOP.
#

from typing import Iterable, Literal

from market_data import MarketSnapshot
from state_machine import StateMachineV2
from intent_authority import IntentAuthority
from execution_router import execute
from execution_audit import create_audit_record
from audit_store import get_audit_store
from kill_switch import kill_active


ExecutionMode = Literal["SIM", "PAPER", "CAPITAL"]


class DeterministicRunner:
    """
    Authoritative deterministic execution runner.

    This class drives the entire trading lifecycle
    using canonical MarketSnapshots.
    """

    def __init__(
        self,
        *,
        state_machine: StateMachineV2,
        intent_authority: IntentAuthority,
        execution_mode: ExecutionMode,
        account_id: str,
    ):
        self.state_machine = state_machine
        self.intent_authority = intent_authority
        self.execution_mode = execution_mode
        self.account_id = account_id
        self.audit = get_audit_store()

    # ==================================================
    # Main deterministic loop
    # ==================================================

    def run(self, snapshots: Iterable[MarketSnapshot]) -> None:
        """
        Run deterministic execution over snapshots.

        No branching.
        No shortcuts.
        Kill-dominant.
        """

        for snapshot in snapshots:

            # --------------------------------------------------
            # Kill dominance
            # --------------------------------------------------
            if kill_active():
                break

            # --------------------------------------------------
            # ENTRY EVALUATION
            # --------------------------------------------------
            if self.state_machine.state.name == "IDLE":
                intent = self.intent_authority.evaluate(snapshot)

                if intent is not None:
                    envelope = self.state_machine.authorize_entry(
                        intent=intent,
                        snapshot=snapshot,
                        execution_mode=self.execution_mode,
                    )

                    result = execute(
                        envelope=envelope,
                        account_id=self.account_id,
                    )

                    self.audit.append(
                        create_audit_record(
                            record_type="DETERMINISTIC_ENTRY_EXECUTED",
                            payload={
                                "intent_id": intent.intent_id,
                                "envelope_hash": envelope.envelope_hash,
                                "status": result.status,
                                "timestamp": snapshot.timestamp_utc.isoformat(),
                            },
                        )
                    )

                    if result.status == "SUBMITTED":
                        self.state_machine.on_position_opened()

            # --------------------------------------------------
            # POSITION MANAGEMENT
            # --------------------------------------------------
            if self.state_machine.state.name == "MANAGING_POSITION":
                exit_envelope = self.state_machine.manage_position(
                    snapshot=snapshot,
                    execution_mode=self.execution_mode,
                )

                if exit_envelope is not None:
                    exit_result = execute(
                        envelope=exit_envelope,
                        account_id=self.account_id,
                    )

                    self.audit.append(
                        create_audit_record(
                            record_type="DETERMINISTIC_EXIT_EXECUTED",
                            payload={
                                "envelope_hash": exit_envelope.envelope_hash,
                                "status": exit_result.status,
                                "timestamp": snapshot.timestamp_utc.isoformat(),
                            },
                        )
                    )

                    if exit_result.status == "SUBMITTED":
                        self.state_machine.on_position_closed()
                        self.state_machine.on_audit_complete()

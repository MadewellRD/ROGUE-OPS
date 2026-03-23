#
# replay_engine.py
#
# Backtest / Replay Unification Engine
# PHASE 17 — ATOMIC (CORE)
#
# Responsible for:
# - Driving the live system with historical MarketSnapshots
# - Enforcing replay == live parity
# - Delegating intent creation to Phase 12 authority
# - Producing deterministic audit records
#
# Explicitly NOT responsible for:
# - Market data ingestion
# - Strategy logic
# - Broker execution
# - Risk or exit decisions
#

from typing import Iterable

from market_data import MarketSnapshot
from state_machine import StateMachineV2
from execution_audit import create_audit_record
from audit_store import get_audit_store
from intent_authority import IntentAuthority


class ReplayEngine:
    """
    Deterministic replay controller.

    Feeds MarketSnapshots into the live
    StateMachine without modification.

    Intent creation is delegated exclusively
    to Phase 12 — IntentAuthority.
    """

    def __init__(
        self,
        *,
        state_machine: StateMachineV2,
        intent_authority: IntentAuthority,
    ):
        """
        Inputs:
            state_machine    : Live StateMachineV2 instance
            intent_authority : Phase 12 IntentAuthority
        """
        self.state_machine = state_machine
        self.intent_authority = intent_authority
        self.audit = get_audit_store()

    # ----------------------------
    # Replay loop
    # ----------------------------

    def run(self, snapshots: Iterable[MarketSnapshot]) -> None:
        """
        Run deterministic replay over snapshots.

        No branching.
        No shortcuts.
        Same path as live.
        """

        for snapshot in snapshots:
            # ----------------------------
            # Phase 12 — Intent evaluation
            # ----------------------------
            intent = self.intent_authority.evaluate(snapshot)

            if intent is not None:
                self.state_machine.authorize_entry(
                    intent=intent,
                    snapshot=snapshot,
                )

                self.audit.append(
                    create_audit_record(
                        record_type="REPLAY_ENTRY_AUTHORIZED",
                        payload={
                            "intent_id": intent.intent_id,
                            "symbol": intent.symbol,
                            "timestamp": snapshot.timestamp_utc.isoformat(),
                        },
                    )
                )

            # ----------------------------
            # Position management
            # ----------------------------
            if self.state_machine.state.name == "MANAGING_POSITION":
                directive = self.state_machine.manage_position(
                    snapshot=snapshot
                )

                if directive is not None:
                    self.audit.append(
                        create_audit_record(
                            record_type="REPLAY_EXIT_TRIGGERED",
                            payload={
                                "reason": directive.reason,
                                "timestamp": snapshot.timestamp_utc.isoformat(),
                            },
                        )
                    )

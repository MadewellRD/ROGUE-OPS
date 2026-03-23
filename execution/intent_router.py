"""
Intent Router
PHASE 9 — Arbitration → LAW → Execution Bridge (With Telemetry)

This module routes arbitrated intents to:
- Simulation (always available)
- Execution (paper / live via StateMachine authorization)

CRITICAL:
- LAW governs all authorization
- StateMachine is the ONLY execution authority
- Router is strategy-agnostic
- Kill-switch enforced
- Telemetry is append-only and non-authoritative
"""

from arbitration.arbitration_types import ArbitrationResult
from governance.kill_switch import kill_active
from sim_golden.simulation_executor import simulate_authorized_intent

from execution.state_machine import StateMachineV2
from execution.execution_driver import execute_and_apply
from market.market_data_adapter_steady import MarketSnapshot

from audit.execution_telemetry_log import log_event


class IntentRouter:
    """
    Routes arbitrated intents through LAW and into execution.
    """

    def __init__(
        self,
        *,
        state_machine: StateMachineV2,
        account_id: str,
        execution_mode: str,
    ):
        self._sm = state_machine
        self._account_id = account_id
        self._execution_mode = execution_mode

    def route(
        self,
        *,
        arbitration_result: ArbitrationResult,
        snapshot: MarketSnapshot,
    ) -> None:
        """
        Route an arbitrated intent.

        Simulation always runs.
        Execution runs ONLY if authorized by StateMachine.
        """

        intent = arbitration_result.intent

        # --------------------------------------------------
        # NO INTENT
        # --------------------------------------------------
        if intent is None:
            log_event(
                event="INTENT_NONE",
                intent_type=None,
                strategy=None,
                execution_mode=self._execution_mode,
            )
            return

        intent_type = type(intent).__name__
        strategy = arbitration_result.winning_strategy

        log_event(
            event="INTENT_SEEN",
            intent_type=intent_type,
            strategy=strategy,
            execution_mode=self._execution_mode,
        )

        # --------------------------------------------------
        # SIMULATION (ALWAYS)
        # --------------------------------------------------
        simulate_authorized_intent(
            intent=intent,
            source_strategy=strategy,
        )

        log_event(
            event="INTENT_SIMULATED",
            intent_type=intent_type,
            strategy=strategy,
            execution_mode=self._execution_mode,
        )

        # --------------------------------------------------
        # EXECUTION SUPPRESSION (KILL)
        # --------------------------------------------------
        if kill_active():
            log_event(
                event="INTENT_SUPPRESSED_KILL",
                intent_type=intent_type,
                strategy=strategy,
                execution_mode=self._execution_mode,
                reason="KILL_ACTIVE",
            )
            return

        # --------------------------------------------------
        # LAW AUTHORIZATION
        # --------------------------------------------------
        try:
            envelope = self._sm.authorize_entry(
                intent=intent,
                snapshot=snapshot,
                execution_mode=self._execution_mode,
            )
        except Exception as e:
            log_event(
                event="INTENT_DENIED_LAW",
                intent_type=intent_type,
                strategy=strategy,
                execution_mode=self._execution_mode,
                reason=str(e),
            )
            return

        log_event(
            event="INTENT_AUTHORIZED",
            intent_type=intent_type,
            strategy=strategy,
            execution_mode=self._execution_mode,
        )

        # --------------------------------------------------
        # EXECUTION
        # --------------------------------------------------
        success = execute_and_apply(
            envelope=envelope,
            state_machine=self._sm,
            account_id=self._account_id,
            entry_price=snapshot.spot,
        )

        log_event(
            event="INTENT_EXECUTED" if success else "INTENT_EXECUTION_FAILED",
            intent_type=intent_type,
            strategy=strategy,
            execution_mode=self._execution_mode,
        )

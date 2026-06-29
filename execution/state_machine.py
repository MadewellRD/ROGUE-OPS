# state_machine.py
#
# ROGUE:OPS State Machine v2 — Position-Aware
#
# PHASE C2 — KILL-DOMINANT, EXIT-SUPREME
# PHASE 26 — ENTRY TIME AUTHORITY (WIRED)
# PHASE 31 — CAPITAL READINESS GATE (WIRED)
#
# This file DOES NOT:
# - Execute broker orders
# - Mutate positions
#
# It ONLY:
# - Enforces lifecycle correctness
# - Authorizes ENTRY / EXIT envelopes
# - Actively asserts kill authority
# - Enforces ENTRY time jurisdiction (Phase 26)
# - Enforces CAPITAL readiness gate (Phase 31)
#

import time
from enum import Enum, auto

from execution.execution_contracts import ExecutionIntent
from execution.execution_envelope import ExecutionEnvelope
from market.market_data import MarketSnapshot
from governance.ops_state import get_ops_state
from governance.kill_switch import kill_active, engage_kill
from advisory.time_authority import evaluate_entry_time

from governance.risk_engine import RiskEngineV2
from execution.position_store import get_position_store
from execution.exit_engine import ExitEngine, ExitDirective


# ==================================================
# System States
# ==================================================

class SystemState(Enum):
    IDLE = auto()
    OPEN_POSITION = auto()
    MANAGING_POSITION = auto()
    EXITING_POSITION = auto()
    POST_TRADE_AUDIT = auto()
    HALTED = auto()


# ==================================================
# State Machine v2
# ==================================================

class StateMachineV2:
    """
    OPS-authoritative, position-aware state machine.

    This machine AUTHORIZES execution.
    The driver EXECUTES execution.
    Kill authority is ASSERTED here.
    """

    def __init__(self, *, ibkr_account_id: str):
        self.ibkr_account_id = ibkr_account_id

        # Authorities
        self.ops = get_ops_state()
        self.risk = RiskEngineV2()
        self.exit_engine = ExitEngine()
        self.positions = get_position_store()

        self.state = SystemState.IDLE

        print("[OK] OPS State Machine READY (Phase C2 + Phase 26 + Phase 31)")

    # ==================================================
    # Inert Control Loop
    # ==================================================

    def run_main_loop(self) -> None:
        print("[OPS] Entering main control loop")

        while True:
            try:
                if self.ops.is_halted() or kill_active():
                    if self.state != SystemState.HALTED:
                        engage_kill(reason="OPS_OR_KILL_DETECTED")
                        self.state = SystemState.HALTED
                    time.sleep(5)
                    continue

                time.sleep(1)

            except KeyboardInterrupt:
                engage_kill(reason="MANUAL_INTERRUPT")
                self.ops.halt(reason="MANUAL_INTERRUPT")
                self.state = SystemState.HALTED

            except Exception as e:
                engage_kill(reason=f"STATE_MACHINE_FAILURE:{e}")
                self.ops.halt(reason="STATE_MACHINE_FAILURE")
                self.state = SystemState.HALTED

    # ==================================================
    # ENTRY AUTHORIZATION
    # ==================================================

    def authorize_entry(
        self,
        *,
        intent: ExecutionIntent,
        snapshot: MarketSnapshot,
        execution_mode: str,
    ) -> ExecutionEnvelope:
        """
        Authorize a new position entry and produce an ENTRY envelope.
        """

        if self.state != SystemState.IDLE:
            raise RuntimeError("System not IDLE")

        if kill_active() or self.ops.is_halted():
            engage_kill(reason="ENTRY_WHILE_HALTED")
            self.ops.halt(reason="KILL_OR_OPS_HALTED")
            self.state = SystemState.HALTED
            raise RuntimeError("OPS HALTED")

        if self.positions.has_open_position():
            raise RuntimeError("Open position already exists")

        # ----------------------------
        # ENTRY Time Authority (PHASE 26)
        # ----------------------------
        allowed, reason = evaluate_entry_time(snapshot.timestamp_utc)
        if not allowed:
            raise RuntimeError(f"ENTRY_TIME_BLOCKED:{reason}")

        # ----------------------------
        # CAPITAL Readiness Gate (PHASE 31)
        # Enforced authoritatively in execution_router.execute_sized() against
        # the sealed ExecutionEnvelope. The prior call here used a stale
        # signature (intent=/ops_state=) and ran before the envelope existed.
        # ----------------------------

        # ----------------------------
        # Risk authority (supreme)
        # ----------------------------
        try:
            self.risk.pre_trade_check(
                intent=intent,
                snapshot=snapshot,
            )
        except Exception as e:
            engage_kill(reason=f"RISK_ENGINE_FAILURE:{e}")
            raise

        envelope = ExecutionEnvelope.create(
            intent=intent,
            action="ENTRY",
            execution_mode=execution_mode,
            ops_state=self.ops.get(),
            risk_ok=True,
            authorized=True,
        )

        self.state = SystemState.OPEN_POSITION
        return envelope

    # ==================================================
    # POSITION OPEN CONFIRMATION
    # ==================================================

    def on_position_opened(self) -> None:
        if self.state != SystemState.OPEN_POSITION:
            engage_kill(reason="INVALID_OPEN_TRANSITION")
            raise RuntimeError("Invalid state transition")

        self.state = SystemState.MANAGING_POSITION

    def on_entry_failed(self) -> None:
        """Recover from an entry that was AUTHORIZED but never opened (broker
        unreachable/rejected, or no fill). `authorize_entry` advances IDLE ->
        OPEN_POSITION before execution; if execution fails, `on_position_opened`
        never fires and the machine would otherwise deadlock in OPEN_POSITION
        (every later entry -> "System not IDLE"). This reverts to IDLE so the
        loop can retry. A failed entry is recoverable, not a safety breach, so
        it does NOT engage the kill. Only acts from OPEN_POSITION; else no-op."""
        if self.state == SystemState.OPEN_POSITION:
            self.state = SystemState.IDLE

    # ==================================================
    # POSITION MANAGEMENT
    # ==================================================

    def manage_position(
        self,
        *,
        snapshot: MarketSnapshot,
        indicators: dict,
        execution_mode: str,
    ) -> ExecutionEnvelope | None:
        """
        Evaluate exit conditions.

        If exit is required, return an EXIT envelope.
        """

        if self.state != SystemState.MANAGING_POSITION:
            engage_kill(reason="MANAGE_WHEN_NOT_MANAGING")
            raise RuntimeError("Invalid manage_position call")

        directive = self.exit_engine.evaluate(
            position=self.positions.get_open_position(),
            snapshot=snapshot,
            indicators=indicators,
            ops_halted=self.ops.is_halted() or kill_active(),
        )

        if directive is None:
            return None

        exit_intent = self.positions.get_open_position().to_exit_intent()

        envelope = ExecutionEnvelope.create(
            intent=exit_intent,
            action="EXIT",
            execution_mode=execution_mode,
            ops_state=self.ops.get(),
            risk_ok=True,
            authorized=True,
        )

        self.state = SystemState.EXITING_POSITION
        return envelope

    # ==================================================
    # EXIT CONFIRMATION
    # ==================================================

    def on_position_closed(self) -> None:
        if self.state != SystemState.EXITING_POSITION:
            engage_kill(reason="INVALID_EXIT_TRANSITION")
            raise RuntimeError("Invalid exit transition")

        self.state = SystemState.POST_TRADE_AUDIT

    # ==================================================
    # AUDIT COMPLETION
    # ==================================================

    def on_audit_complete(self) -> None:
        if self.state != SystemState.POST_TRADE_AUDIT:
            engage_kill(reason="INVALID_AUDIT_TRANSITION")
            raise RuntimeError("Audit not complete")

        self.state = SystemState.IDLE

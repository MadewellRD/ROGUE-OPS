#
# execution/execution_driver.py
#
# Execution Driver
# PHASE C1 + PHASE 60 + PHASE 8 — CAPITAL GO / NO-GO ENFORCED
#
# Responsible for:
# - Executing immutable execution envelopes
# - Dispatching authoritative position mutations
# - Enforcing realized loss limits (CAPITAL only)
# - Enforcing one-time CAPITAL preflight (fail-closed)
#
# Explicitly NOT responsible for:
# - Strategy
# - Risk logic (beyond enforcement)
# - Market data
#

import os
from typing import Optional

from execution.execution_router import execute
from execution.execution_position_bridge import ExecutionPositionBridge
from execution.execution_envelope import ExecutionEnvelope
from execution.state_machine import StateMachineV2

from governance.kill_switch import kill_active
from capital.capital_preflight import run_capital_preflight
from capital.daily_loss_governor import record_realized_pnl


# ==================================================
# CAPITAL PREFLIGHT LATCH (PROCESS-LOCAL)
# ==================================================

_CAPITAL_ARMED: bool = False


def _ensure_capital_armed() -> None:
    """
    Enforce one-time CAPITAL preflight.

    - Idempotent per process
    - Fail-closed
    - Irreversible until restart
    """

    global _CAPITAL_ARMED

    if _CAPITAL_ARMED:
        return

    # Hard dominance
    if kill_active():
        raise RuntimeError("CAPITAL_EXECUTION_BLOCKED:KILL_ACTIVE")

    execution_mode = os.getenv("EXECUTION_MODE")
    if execution_mode != "CAPITAL":
        raise RuntimeError(
            f"CAPITAL_EXECUTION_BLOCKED:INVALID_EXECUTION_MODE:{execution_mode}"
        )

    # This MUST raise on failure
    run_capital_preflight()

    _CAPITAL_ARMED = True
    print("[CAPITAL] Capital execution ARMED (preflight passed)")


# ==================================================
# EXECUTION ENTRYPOINT
# ==================================================

def execute_and_apply(
    *,
    envelope: ExecutionEnvelope,
    state_machine: StateMachineV2,
    account_id: str,
    entry_price: Optional[float] = None,
) -> bool:
    """
    Canonical execution + position mutation path.

    Returns:
        True if execution and position update succeeded, else False.
    """

    # --------------------------------------------------
    # CAPITAL HARD GATE (PHASE 8)
    # --------------------------------------------------
    if envelope.execution_mode == "CAPITAL":
        try:
            _ensure_capital_armed()
        except Exception as e:
            print(f"[CAPITAL][DENY] {e}")
            return False

    # --------------------------------------------------
    # EXECUTION (AUTHORITATIVE)
    # --------------------------------------------------
    try:
        result = execute(envelope, account_id)
    except Exception as e:
        print(f"[ERROR] Execution failed for envelope {envelope.id}: {e}")
        return False

    # --------------------------------------------------
    # POSITION MUTATION + P&L
    # --------------------------------------------------
    bridge = ExecutionPositionBridge(state_machine=state_machine)

    if envelope.action == "ENTRY":
        if entry_price is None:
            print("[ERROR] Missing entry_price for ENTRY action.")
            return False

        bridge.handle_entry(
            envelope=envelope,
            fill_price=entry_price,
            result=result,
        )

    elif envelope.action == "EXIT":
        bridge.handle_exit(
            envelope=envelope,
            result=result,
        )

        # CAPITAL ONLY — realized loss governance
        if envelope.execution_mode == "CAPITAL":
            record_realized_pnl(
                account_id=account_id,
                envelope=envelope,
            )

    return True

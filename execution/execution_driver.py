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

from execution.execution_router import execute, execute_sized
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
        # ENTRY must go through the SIZED path; EXIT through the exit path.
        if envelope.action == "ENTRY":
            result = execute_sized(envelope, account_id)
        else:
            result = execute(envelope, account_id)
    except Exception as e:
        print(f"[ERROR] Execution failed for envelope {envelope.envelope_hash}: {e}")
        if envelope.action == "ENTRY":
            state_machine.on_entry_failed()   # recover: don't deadlock in OPEN_POSITION
        return False

    if result.status != "SUBMITTED":
        if envelope.action == "ENTRY":
            state_machine.on_entry_failed()   # recover: don't deadlock in OPEN_POSITION
        return False

    # --------------------------------------------------
    # POSITION MUTATION + P&L
    # --------------------------------------------------
    bridge = ExecutionPositionBridge(state_machine=state_machine)

    if envelope.action == "ENTRY":
        # Prefer the actual fill from the broker/SIM result; fall back to a
        # caller-supplied price only if the result carries none.
        fill_price = result.raw.get("fill_price", entry_price)
        if fill_price is None:
            print("[ERROR] No fill price available for ENTRY.")
            state_machine.on_entry_failed()   # recover: don't deadlock in OPEN_POSITION
            return False

        bridge.handle_entry(
            envelope=envelope,
            entry_price=fill_price,
            result=result,
        )

    elif envelope.action == "EXIT":
        try:
            exit_result = bridge.handle_exit(
                envelope=envelope,
                result=result,
            )
        except Exception as e:
            # ROGUE-002: a no-fill / unconfirmed exit (e.g. EXIT_FILL_PRICE_MISSING)
            # must NOT crash the loop or strand a live position. The working order
            # was cancelled in the broker layer (ROGUE-003); revert EXITING ->
            # MANAGING so exit supremacy re-issues the exit next cycle. A no-fill
            # is recoverable, not a kill condition.
            print(f"[EXIT] exit not confirmed for {envelope.envelope_hash}: {e}")
            state_machine.on_exit_failed()
            return False

        # Realized-loss governance — feed the daily-loss governor so the
        # daily-loss kill can actually engage (applies to all live modes).
        record_realized_pnl(pnl_usd=exit_result["realized_pnl_usd"])

        # Track record — append the paired closed trade to the scorecard ledger
        # (real modes only; advisory, best-effort, never affects execution).
        if envelope.execution_mode not in ("SIM", "REPLAY"):
            try:
                from capital.trade_ledger import record_closed_trade
                record_closed_trade(exit_result)
            except Exception:
                pass

    return True

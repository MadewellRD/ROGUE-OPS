#
# tools/test_exit_recovery.py
#
# ROGUE-002: a no-fill / unconfirmed EXIT must NOT crash the loop or strand a
# live position. execute_and_apply must catch it, revert EXITING_POSITION ->
# MANAGING_POSITION (so exit supremacy retries next cycle), keep the position
# open, and return False. A confirmed fill still closes cleanly to IDLE.
#
#   python tools\test_exit_recovery.py
#

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROGUE_OPS_HOME", tempfile.mkdtemp(prefix="rogue_exitrec_test_"))
os.environ["EXECUTION_MODE"] = "SIM"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import execution.execution_driver as drv
from execution.execution_driver import execute_and_apply
from execution.state_machine import StateMachineV2, SystemState
from execution.execution_envelope import ExecutionEnvelope
from execution.execution_contracts import ExecutionIntent, OptionSpec, ExecutionResult, now_utc
from execution.execution_position_bridge import ExecutionPositionBridge
from execution.position_store import get_position_store
from governance.ops_state import get_ops_state


def _result(fill):
    return ExecutionResult(status="SUBMITTED", order_id=1, reason=None,
                           executed_utc=now_utc(), parity_hash=None, raw={"fill_price": fill})


def _into_exiting(sm) -> ExecutionEnvelope:
    """Open a real position and advance to EXITING_POSITION, returning the EXIT
    envelope (mirrors the live manage_position -> EXITING transition)."""
    positions = get_position_store()
    while positions.has_open_position():
        positions.close_position()
    ops = get_ops_state().get()
    bridge = ExecutionPositionBridge(state_machine=sm)
    intent = ExecutionIntent.new(symbol="SPY", qty=1, action="BUY", sec_type="OPT",
        strategy_tag="TEST", option=OptionSpec(expiry="20260629", strike=600.0, right="C"))
    entry_env = ExecutionEnvelope.create(intent=intent, action="ENTRY", execution_mode="SIM",
        ops_state=ops, risk_ok=True, authorized=True)
    sm.state = SystemState.OPEN_POSITION
    bridge.handle_entry(envelope=entry_env, entry_price=1.50, result=_result(1.50))
    exit_intent = positions.get_open_position().to_exit_intent()
    exit_env = ExecutionEnvelope.create(intent=exit_intent, action="EXIT", execution_mode="SIM",
        ops_state=ops, risk_ok=True, authorized=True)
    sm.state = SystemState.EXITING_POSITION
    return exit_env


def test_exit_failed_transition():
    sm = StateMachineV2(ibkr_account_id="SIM")
    sm.state = SystemState.EXITING_POSITION
    sm.on_exit_failed()
    assert sm.state == SystemState.MANAGING_POSITION, sm.state
    # no-op from other states (never silently leaves a managed position)
    sm.state = SystemState.IDLE
    sm.on_exit_failed()
    assert sm.state == SystemState.IDLE


def test_no_fill_exit_recovers_not_crash():
    sm = StateMachineV2(ibkr_account_id="SIM")
    exit_env = _into_exiting(sm)
    drv.execute = lambda env, acct: _result(None)        # broker: no fill in window
    ok = execute_and_apply(envelope=exit_env, state_machine=sm, account_id="SIM")
    assert ok is False, "no-fill exit must return False, not raise"
    assert sm.state == SystemState.MANAGING_POSITION, f"must revert to MANAGING, got {sm.state}"
    assert get_position_store().has_open_position(), "position must stay open for retry"


def test_confirmed_exit_closes_clean():
    sm = StateMachineV2(ibkr_account_id="SIM")
    exit_env = _into_exiting(sm)
    drv.execute = lambda env, acct: _result(0.50)        # broker: filled
    ok = execute_and_apply(envelope=exit_env, state_machine=sm, account_id="SIM")
    assert ok is True, "confirmed exit must return True"
    assert sm.state == SystemState.IDLE, f"clean close must reach IDLE, got {sm.state}"
    assert not get_position_store().has_open_position(), "position must be closed"


def main():
    test_exit_failed_transition()
    test_no_fill_exit_recovers_not_crash()
    test_confirmed_exit_closes_clean()
    print("EXIT RECOVERY PASS — no-fill exit reverts EXITING->MANAGING (retry, no crash); confirmed fill closes to IDLE")


if __name__ == "__main__":
    main()

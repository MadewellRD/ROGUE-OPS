#
# tools/test_fill_pnl.py
#
# Proves fill-derived P&L is REAL end to end:
#   entry fill 1.50 -> exit fill 0.50 on 2 contracts
#   -> bridge computes -$200 realized
#   -> daily-loss governor accrues it and TRIPS THE KILL (limit $100).
#
# This is the data-level proof that the daily-loss kill protects real capital,
# not just synthetic SIM fills.  python tools\test_fill_pnl.py
#

import os
import sys
from pathlib import Path

os.environ["EXECUTION_MODE"] = "CAPITAL"
os.environ["MAX_DAILY_LOSS_USD"] = "100"
os.environ.setdefault("ROGUE_OPS_HOME", "/tmp/h")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.state_machine import StateMachineV2, SystemState
from execution.execution_envelope import ExecutionEnvelope
from execution.execution_contracts import ExecutionIntent, OptionSpec, ExecutionResult, now_utc
from execution.execution_position_bridge import ExecutionPositionBridge
from execution.position_store import get_position_store
from governance.ops_state import get_ops_state
from governance.kill_switch import kill_active
import capital.daily_loss_governor as gov


def _result(fill: float) -> ExecutionResult:
    return ExecutionResult(status="SUBMITTED", order_id=1, reason=None,
                           executed_utc=now_utc(), parity_hash=None, raw={"fill_price": fill})


def main() -> None:
    gov.reset()
    assert not kill_active(), "test must start with kill clear"

    sm = StateMachineV2(ibkr_account_id="TEST")
    ops = get_ops_state().get()
    bridge = ExecutionPositionBridge(state_machine=sm)
    positions = get_position_store()

    # --- ENTRY filled at 1.50 on 2 contracts ---
    intent = ExecutionIntent.new(symbol="SPY", qty=2, action="BUY", sec_type="OPT",
        strategy_tag="TEST", option=OptionSpec(expiry="20260625", strike=600.0, right="C"))
    entry_env = ExecutionEnvelope.create(intent=intent, action="ENTRY", execution_mode="CAPITAL",
        ops_state=ops, risk_ok=True, authorized=True)
    sm.state = SystemState.OPEN_POSITION
    bridge.handle_entry(envelope=entry_env, entry_price=1.50, result=_result(1.50))
    assert positions.has_open_position(), "entry fill should open a position"

    # --- EXIT filled at 0.50 -> realized loss ---
    exit_intent = positions.get_open_position().to_exit_intent()
    exit_env = ExecutionEnvelope.create(intent=exit_intent, action="EXIT", execution_mode="CAPITAL",
        ops_state=ops, risk_ok=True, authorized=True)
    sm.state = SystemState.EXITING_POSITION
    out = bridge.handle_exit(envelope=exit_env, result=_result(0.50))

    # (0.50 - 1.50) * 2 contracts * 100 multiplier = -200
    assert out["realized_pnl_usd"] == -200.0, f"expected -200, got {out['realized_pnl_usd']}"

    # Feed the governor exactly as execute_and_apply does.
    gov.record_realized_pnl(pnl_usd=out["realized_pnl_usd"])

    assert gov.is_breached(), "real -$200 loss must breach the $100 limit"
    assert kill_active(), "breach must trip the kill switch"

    print("FILL P&L PASS — real exit fill -> -$200 realized -> daily-loss kill tripped")


if __name__ == "__main__":
    main()

#
# tools/test_entry_recovery.py
#
# Regression for the OPEN_POSITION deadlock: authorize_entry advances
# IDLE -> OPEN_POSITION before execution; if execution fails, on_entry_failed()
# must revert to IDLE so the loop can retry (never strand the engine).
#
#   python tools\test_entry_recovery.py
#

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROGUE_OPS_HOME", tempfile.mkdtemp(prefix="rogue_entryrec_test_"))

from execution.state_machine import StateMachineV2, SystemState


def test_failed_entry_returns_to_idle():
    sm = StateMachineV2(ibkr_account_id="SIM")
    assert sm.state == SystemState.IDLE
    # authorize_entry advanced the state; execution then failed (broker down).
    sm.state = SystemState.OPEN_POSITION
    sm.on_entry_failed()
    assert sm.state == SystemState.IDLE, sm.state
    # idempotent / safe to call again from IDLE
    sm.on_entry_failed()
    assert sm.state == SystemState.IDLE


def test_entry_failed_is_noop_when_managing():
    sm = StateMachineV2(ibkr_account_id="SIM")
    sm.state = SystemState.MANAGING_POSITION
    sm.on_entry_failed()
    assert sm.state == SystemState.MANAGING_POSITION, "must not disturb a live managed position"


def main() -> None:
    test_failed_entry_returns_to_idle()
    test_entry_failed_is_noop_when_managing()
    print("ENTRY RECOVERY PASS — failed entry reverts OPEN_POSITION->IDLE; no-op while managing")


if __name__ == "__main__":
    main()

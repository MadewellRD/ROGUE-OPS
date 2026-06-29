#
# tools/test_arm_gate.py
#
# ROGUE-009: operator ARM gate. PAPER/CAPITAL entries require an explicit ARM
# (durable file written by the console ARM button); SIM is exempt. This proves
# the console ARM is a real control, not cosmetic.
#
#   python tools\test_arm_gate.py
#

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("ROGUE_OPS_HOME", tempfile.mkdtemp(prefix="rogue_arm_test_"))

from governance.paths import ops_home
from governance.arm_switch import arm_active
from execution.state_machine import StateMachineV2


class _Snap:
    # Out-of-window timestamp: an armed/exempt path stops at the ENTRY time gate,
    # never reaching risk or engaging the kill — keeps the test isolated.
    timestamp_utc = "2026-06-29T02:00:00Z"


def _arm(on: bool):
    p = ops_home() / "ARM"
    if on:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("armed", encoding="utf-8")
    elif p.exists():
        p.unlink()


def _authorize_err(mode: str) -> str:
    sm = StateMachineV2(ibkr_account_id="SIM")
    try:
        sm.authorize_entry(intent=None, snapshot=_Snap(), execution_mode=mode)
        return ""
    except Exception as e:
        return str(e)


def test_arm_file_roundtrip():
    _arm(False); assert arm_active() is False
    _arm(True); assert arm_active() is True
    _arm(False); assert arm_active() is False


def test_paper_denied_when_disarmed():
    _arm(False)
    assert "NOT_ARMED" in _authorize_err("PAPER")


def test_capital_denied_when_disarmed():
    _arm(False)
    assert "NOT_ARMED" in _authorize_err("CAPITAL")


def test_paper_passes_arm_gate_when_armed():
    _arm(True)
    # Gate opens; it then stops at the time authority (out-of-window), NOT on ARM.
    assert "NOT_ARMED" not in _authorize_err("PAPER")
    _arm(False)


def test_sim_is_exempt():
    _arm(False)
    assert "NOT_ARMED" not in _authorize_err("SIM")


def main():
    test_arm_file_roundtrip()
    test_paper_denied_when_disarmed()
    test_capital_denied_when_disarmed()
    test_paper_passes_arm_gate_when_armed()
    test_sim_is_exempt()
    print("ARM GATE PASS — PAPER/CAPITAL require ARM; SIM exempt; file round-trip")


if __name__ == "__main__":
    main()

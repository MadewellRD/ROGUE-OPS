#
# tools/test_console.py
#
# Offline, deterministic tests for the unified console surface (no network):
#   - the durable kill FILE drives kill_active() independent of in-process state
#     (the cross-process property the browser kill button relies on),
#   - the ARM intent flag round-trips,
#   - control.run_research returns charting-ready shape (Massive mocked).
#
#   python tools\test_console.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance import kill_switch
from api import control


def test_kill_file_is_cross_process():
    # fresh: no in-process kill, no env, no file
    kill_switch.clear_kill_file()
    assert kill_switch._kill_file_present() is False
    assert kill_switch.kill_active() is False, "should not be killed before anything is engaged"

    # write the file WITHOUT touching in-process state (simulates another process)
    kill_switch._write_kill_file("test: another process engaged kill")
    assert kill_switch._kill_file_present() is True
    assert kill_switch.kill_active() is True, "the kill FILE alone must trigger kill (cross-process)"

    # operator clears the file; with no in-process kill set, we are clear again
    assert kill_switch.clear_kill_file() is True
    assert kill_switch.kill_active() is False, "clearing the file resumes (no in-process kill was set)"


def test_arm_flag_round_trips():
    control.set_arm(False)
    assert control.arm_state() is False
    r = control.set_arm(True)
    assert r["ok"] and r["armed"] is True
    assert control.arm_state() is True
    control.set_arm(False)
    assert control.arm_state() is False


def test_research_daily_shape():
    from market import market_data_massive as M

    # synthetic daily bars: a gentle zig-zag so at least one strategy trades
    bars = []
    base = 1_700_000_000
    for i in range(160):
        c = 100.0 + 6.0 * (1 + (i % 20 - 10) / 10.0)  # oscillating
        bars.append(M.Bar(t_ms=(base + i * 86400) * 1000, open=c, high=c + 0.6, low=c - 0.6, close=c, volume=1_000_000 + i))

    orig = M.daily_bars
    M.daily_bars = lambda *a, **k: bars
    try:
        res = control.run_research("SPY", days=160, cost_bps=2.0, source="massive_daily")
    finally:
        M.daily_bars = orig

    assert res["ok"] is True and res["source"] == "massive_daily"
    assert res["bars"] == 160
    assert len(res["price"]) == 160 and "close" in res["price"][0] and "date" in res["price"][0]
    assert res["strategies"], "expected candidate strategies"

    for s in res["strategies"]:
        for k in ("name", "note", "metrics", "in_sample", "out_of_sample", "trades", "equity"):
            assert k in s, f"strategy missing key {k}"
        assert s["equity"] and s["equity"][0]["equity"] == 1.0, "equity curve must anchor at 1.0"

    oos = [s["out_of_sample"]["cum_return"] for s in res["strategies"]]
    assert oos == sorted(oos, reverse=True), "strategies must be ranked by out-of-sample cumulative"


def main() -> None:
    test_kill_file_is_cross_process()
    test_arm_flag_round_trips()
    test_research_daily_shape()
    print("CONSOLE PASS — cross-process kill file, arm flag round-trip, research shape (massive mocked)")


if __name__ == "__main__":
    main()

#
# tools/test_backtest.py
#
# Offline, deterministic tests for the backtest harness logic (no network).
#   python tools\test_backtest.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.backtest import example_long_entry, example_exit, simulate, stats


def _req(ema9, ema21, macd, rsi7):
    return {"EMA(9)": ema9, "EMA(21)": ema21, "MACD_Histogram": macd, "RSI(7)": rsi7}


def main() -> None:
    # --- entry rule ---
    assert example_long_entry(_req(2, 1, 0.5, 55), True) is True, "uptrend, momentum, not overbought -> enter"
    assert example_long_entry(_req(2, 1, 0.5, 55), False) is False, "not passed -> no entry"
    assert example_long_entry(_req(2, 1, 0.5, 72), True) is False, "overbought -> no entry"
    assert example_long_entry(_req(1, 2, 0.5, 55), True) is False, "downtrend -> no entry"
    assert example_long_entry({}, True) is False, "missing keys -> no entry"

    # --- exit rule ---
    assert example_exit(_req(2, 1, 0.5, 72)) is True, "overbought -> exit"
    assert example_exit(_req(1, 2, -0.1, 40)) is True, "trend flip -> exit"
    assert example_exit(_req(2, 1, 0.5, 55)) is False, "healthy uptrend -> hold"
    assert example_exit({}) is True, "missing keys -> fail-safe exit"

    # --- simulate + stats (one win, one loss) ---
    rows = [
        {"date": "d1", "close": 100.0, "req": _req(2, 1, 0.5, 55), "passed": True},   # enter
        {"date": "d2", "close": 110.0, "req": _req(1, 2, -0.1, 40), "passed": True},  # exit +10%
        {"date": "d3", "close": 110.0, "req": _req(2, 1, 0.5, 55), "passed": True},   # enter
        {"date": "d4", "close": 99.0,  "req": _req(1, 2, -0.1, 40), "passed": True},  # exit -10%
    ]
    trades = simulate(rows)
    assert len(trades) == 2, f"expected 2 trades, got {len(trades)}"
    assert abs(trades[0]["ret"] - 0.10) < 1e-9, "first trade +10%"
    assert abs(trades[1]["ret"] + 0.10) < 1e-9, "second trade -10%"

    s = stats(trades)
    assert s["trades"] == 2 and s["wins"] == 1, "two trades, one win"
    assert abs(s["win_rate"] - 0.5) < 1e-9, "50% win rate"
    assert abs(s["cum_return"] - (1.10 * 0.90 - 1.0)) < 1e-9, "compounded return"
    assert s["max_drawdown"] <= 0.0, "drawdown is non-positive"

    # no entries when never 'passed' (fail-closed)
    assert simulate([{"date": "x", "close": 1.0, "req": _req(2, 1, 0.5, 55), "passed": False}]) == []

    print("BACKTEST PASS — entry/exit rules, trade simulation, and stats are correct")


if __name__ == "__main__":
    main()

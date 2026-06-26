#
# tools/test_intraday.py
#
# Offline, deterministic tests for the intraday-faithful backtest (no network):
# session detection, per-session indicator reset, entry window / hard exit, and
# no-overnight holds. Uses synthetic bars.
#   python tools\test_intraday.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_massive import Bar
from research.intraday import replay_intraday, simulate_intraday
from research.strategies import INTRADAY_CANDIDATES

ORB = next(s for s in INTRADAY_CANDIDATES if s.name == "orb_long")


def _session(t0, prices):
    out = []
    for i, p in enumerate(prices):
        out.append(Bar(t_ms=(t0 + i * 300) * 1000, open=p, high=p + 0.5, low=p - 0.5, close=p, volume=1000 + i))
    return out


def main() -> None:
    base = 1_700_000_000
    # session 1: opening range ~100, then a breakout up (triggers ORB)
    s1 = _session(base, [100.0] * 7 + [101.0 + 0.1 * i for i in range(73)])
    # session 2 (next day -> large gap): flat, no breakout
    s2 = _session(base + 86400, [100.0] * 7 + [100.4] * 73)
    rows = replay_intraday("SPY", s1 + s2, bar_minutes=5)

    # two sessions detected
    sessions = sorted({r["session"] for r in rows})
    assert sessions == [0, 1], f"expected 2 sessions, got {sessions}"

    # indicators reset each session: first bar of session 2 not yet warmed
    s2_first = next(r for r in rows if r["session"] == 1)
    assert s2_first["passed"] is False, "indicators must reset at each session"

    # window + hard-exit flags exist and are bounded correctly
    assert any(r["in_window"] for r in rows) and any(r["hard_exit"] for r in rows)
    for r in rows:
        if r["hard_exit"]:
            assert r["req"]["mins"] >= 385
        if r["in_window"]:
            assert 30 <= r["req"]["mins"] <= 300

    # ORB produces >=1 trade, and NO trade is held across sessions (0DTE)
    trades = simulate_intraday(rows, ORB, cost_bps=1.0)
    assert len(trades) >= 1, "opening-range breakout should trigger at least one trade"
    for t in trades:
        es = rows[int(t.entry_date)]["session"]
        xs = rows[int(t.exit_date)]["session"]
        assert es == xs, "no overnight holds — entry and exit must share a session"

    print("INTRADAY PASS — session reset, entry window/hard-exit, ORB trade, no overnight holds")


if __name__ == "__main__":
    main()

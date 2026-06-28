#
# tools/test_trade_ledger.py
#
# Offline tests for paired-trade accounting + the scorecard (no network/broker):
#   - scorecard math (win rate, expectancy, avg win/loss, best/worst, gross),
#   - cumulative equity curve + max drawdown,
#   - per-day aggregation,
#   - empty-safe,
#   - record -> read round-trip on the shared ledger.
#
#   python tools\test_trade_ledger.py
#

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["ROGUE_OPS_HOME"] = tempfile.mkdtemp(prefix="rogue_tradeledger_test_")

from capital.trade_ledger import record_closed_trade, read_ledger, scorecard


def _row(pnl, day):
    return {"realized_pnl_usd": pnl, "symbol": "SPY", "closed_at_utc": f"{day}T15:55:00Z"}


def test_scorecard_math():
    rows = [
        _row(100.0, "2026-06-29"),
        _row(-50.0, "2026-06-29"),
        _row(30.0, "2026-06-29"),
        _row(-20.0, "2026-06-30"),
        _row(40.0, "2026-06-30"),
    ]
    m = scorecard(rows)
    assert m["trades"] == 5
    assert m["wins"] == 3 and m["losses"] == 2
    assert m["win_rate"] == 0.6
    assert m["gross_pnl_usd"] == 100.0
    assert m["expectancy_usd"] == 20.0
    assert m["avg_win_usd"] == 56.67 and m["avg_loss_usd"] == -35.0
    assert m["best_usd"] == 100.0 and m["worst_usd"] == -50.0
    # cumulative equity: 0,100,50,80,60,100 -> deepest trough is -50 vs peak 100
    assert m["max_drawdown_usd"] == -50.0
    assert m["equity_curve"][-1]["cum"] == 100.0 and len(m["equity_curve"]) == 6
    assert m["by_day"] == {"2026-06-29": 80.0, "2026-06-30": 20.0}


def test_empty_safe():
    m = scorecard([])
    assert m["trades"] == 0
    assert m["win_rate"] is None and m["expectancy_usd"] is None
    assert m["max_drawdown_usd"] == 0.0
    assert m["equity_curve"] == [{"i": 0, "cum": 0.0}]


def test_record_read_round_trip():
    before = len(read_ledger(10_000))
    rec = record_closed_trade({"realized_pnl_usd": 42.5, "symbol": "SPY", "right": "C",
                               "entry_price": 1.20, "exit_price": 1.63, "quantity": 1})
    assert rec is not None and "ts_utc" in rec
    rows = read_ledger(10_000)
    assert len(rows) == before + 1
    assert rows[-1]["realized_pnl_usd"] == 42.5 and rows[-1]["symbol"] == "SPY"
    # and it scores
    assert scorecard(rows)["gross_pnl_usd"] >= 42.5


def main() -> None:
    test_scorecard_math()
    test_empty_safe()
    test_record_read_round_trip()
    print("TRADE LEDGER PASS — scorecard math, equity/drawdown, by-day, empty-safe, record/read round-trip")


if __name__ == "__main__":
    main()

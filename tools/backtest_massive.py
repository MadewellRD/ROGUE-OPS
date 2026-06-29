#
# tools/backtest_massive.py
#
# Intraday-faithful backtest on MASSIVE intraday bars (Options-Basic tier) —
# no TWS required. Same session-window / hard-exit / no-overnight discipline and
# walk-forward split as the IBKR path; just a different (larger, TWS-free) source.
#
#   python tools\backtest_massive.py SPY 60 5 1
#     symbol  lookback_days  bar_minutes  cost_bps
#
# Underlying-return proxy net of cost — directional signal quality, not option
# P&L. (Real option-priced backtest is the next step now that option aggs are
# entitled.)
#

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_massive import intraday_bars
from research.intraday import replay_intraday, simulate_intraday, walk_forward_intraday, keep_rth
from research.engine import metrics
from research.strategies import INTRADAY_CANDIDATES


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "SPY").upper()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    bar_minutes = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    cost_bps = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    today = dt.datetime.now(dt.timezone.utc).date()
    date_from = (today - dt.timedelta(days=days)).isoformat()
    date_to = today.isoformat()

    raw = intraday_bars(symbol, date_from, date_to, multiplier=bar_minutes, timespan="minute")
    if not raw:
        raise SystemExit("No bars returned from Massive (check tier/entitlement/date range).")
    bars = keep_rth(raw)
    print(f"    fetched {len(raw)} bars; {len(bars)} RTH bars after filter")
    rows = replay_intraday(symbol, bars, bar_minutes=bar_minutes)
    sessions = len({r["session"] for r in rows})

    print(f"\n=== {symbol} MASSIVE {bar_minutes}min x {days}D — {len(rows)} bars, {sessions} sessions, cost {cost_bps:g}bps rt ===")
    print(f"    entries 10:00-14:30 ET, hard exit 15:55, no overnight, indicators reset each session")
    print(f"{'strategy':<14}{'trades':>7}{'win%':>7}{'exp%':>9}{'cum%':>9}{'maxDD%':>8}{'OOScum%':>9}{'OOStr':>7}")
    ranked = []
    for s in INTRADAY_CANDIDATES:
        m = metrics(simulate_intraday(rows, s, cost_bps))
        oos = walk_forward_intraday(rows, s, 0.6, cost_bps)["out_of_sample"]
        ranked.append((s.name, m, oos))
    ranked.sort(key=lambda x: x[2]["cum_return"], reverse=True)
    for name, m, oos in ranked:
        print(f"{name:<14}{m['trades']:>7}{m['win_rate']*100:>6.0f}%{m['avg_return']*100:>8.3f}%"
              f"{m['cum_return']*100:>8.2f}%{m['max_drawdown']*100:>7.1f}%{oos['cum_return']*100:>8.2f}%{oos['trades']:>7}")
    print("  ranked by out-of-sample cumulative. Underlying proxy, not option P&L. Small samples = noise.")


if __name__ == "__main__":
    main()

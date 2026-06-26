#
# tools/evaluate_strategies.py
#
# Rank candidate strategies on real Massive daily history, with walk-forward
# (in-sample vs out-of-sample). Live network call (needs a Massive key).
#
#   python tools\evaluate_strategies.py 500 2
#   (args: lookback trading days, round-trip cost in bps)
#

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_massive import daily_bars
from research.engine import replay, simulate, metrics, walk_forward
from research.strategies import CANDIDATES


def run(symbol: str, days: int, cost_bps: float) -> None:
    to = dt.datetime.now(dt.timezone.utc).date()
    frm = to - dt.timedelta(days=int(days * 1.6) + 15)
    bars = daily_bars(symbol, frm.isoformat(), to.isoformat())[-days:]
    if not bars:
        print(f"{symbol}: no bars")
        return
    rows = replay(symbol, bars)

    print(f"\n=== {symbol} — {len(rows)} bars ({rows[0]['date']}..{rows[-1]['date']}), cost {cost_bps:g}bps rt ===")
    print(f"{'strategy':<14}{'trades':>7}{'win%':>7}{'exp%':>8}{'cum%':>9}{'maxDD%':>8}{'OOScum%':>9}{'OOStr':>7}")
    ranked = []
    for s in CANDIDATES:
        m = metrics(simulate(rows, s, cost_bps))
        oos = walk_forward(rows, s, 0.6, cost_bps)["out_of_sample"]
        ranked.append((s.name, m, oos))
    ranked.sort(key=lambda x: x[2]["cum_return"], reverse=True)
    for name, m, oos in ranked:
        print(f"{name:<14}{m['trades']:>7}{m['win_rate']*100:>6.0f}%{m['avg_return']*100:>7.2f}%"
              f"{m['cum_return']*100:>8.2f}%{m['max_drawdown']*100:>7.1f}%{oos['cum_return']*100:>8.2f}%{oos['trades']:>7}")
    print("  ranked by OUT-OF-SAMPLE cumulative; exp% = avg per-trade (underlying, net cost). Daily proxy, not option P&L.")


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    cost = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    for symbol in ("SPY", "IWM"):
        run(symbol, days, cost)


if __name__ == "__main__":
    main()

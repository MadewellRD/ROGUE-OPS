#
# tools/backtest_ibkr.py
#
# Run the strategy research framework on IBKR INTRADAY history (the 0DTE-
# relevant timeframe). Same engine, strategies, and walk-forward discipline as
# the daily backtest — just fed intraday bars from IBKR. Needs TWS running.
#
#   python tools\backtest_ibkr.py SPY "10 D" "5 mins" 1
#   (args: symbol, IBKR duration, bar size, round-trip cost bps)
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_ibkr_history import fetch_bars
from research.engine import replay, simulate, metrics, walk_forward
from research.strategies import CANDIDATES


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    duration = sys.argv[2] if len(sys.argv) > 2 else "10 D"
    bar_size = sys.argv[3] if len(sys.argv) > 3 else "5 mins"
    cost_bps = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    bars = fetch_bars(symbol, duration=duration, bar_size=bar_size)
    if not bars:
        raise SystemExit("No bars returned from IBKR.")
    rows = replay(symbol, bars)

    print(f"\n=== {symbol} IBKR {bar_size} x {duration} — {len(rows)} bars, cost {cost_bps:g}bps rt ===")
    print(f"{'strategy':<14}{'trades':>7}{'win%':>7}{'exp%':>8}{'cum%':>9}{'maxDD%':>8}{'OOScum%':>9}{'OOStr':>7}")
    ranked = []
    for s in CANDIDATES:
        m = metrics(simulate(rows, s, cost_bps))
        oos = walk_forward(rows, s, 0.6, cost_bps)["out_of_sample"]
        ranked.append((s.name, m, oos))
    ranked.sort(key=lambda x: x[2]["cum_return"], reverse=True)
    for name, m, oos in ranked:
        print(f"{name:<14}{m['trades']:>7}{m['win_rate']*100:>6.0f}%{m['avg_return']*100:>7.3f}%"
              f"{m['cum_return']*100:>8.2f}%{m['max_drawdown']*100:>7.1f}%{oos['cum_return']*100:>8.2f}%{oos['trades']:>7}")
    print("  ranked by out-of-sample cumulative. Intraday underlying proxy (continuous indicators across sessions).")


if __name__ == "__main__":
    main()

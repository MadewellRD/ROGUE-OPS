#
# tools/backtest_ibkr.py
#
# Intraday-faithful backtest on IBKR history: per-session indicator reset, the
# live 10:00-14:30 ET entry window, 15:55 hard exit, no overnight holds. Same
# walk-forward discipline. Needs TWS running.
#
#   python tools\backtest_ibkr.py SPY "10 D" "5 mins" 1
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_ibkr_history import fetch_bars
from research.intraday import replay_intraday, simulate_intraday, walk_forward_intraday
from research.strategies import INTRADAY_CANDIDATES


def _bar_minutes(bar_size: str) -> int:
    parts = bar_size.split()
    n = int(parts[0])
    unit = parts[1] if len(parts) > 1 else "mins"
    return n * 60 if "hour" in unit else n


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    duration = sys.argv[2] if len(sys.argv) > 2 else "10 D"
    bar_size = sys.argv[3] if len(sys.argv) > 3 else "5 mins"
    cost_bps = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    bars = fetch_bars(symbol, duration=duration, bar_size=bar_size)
    if not bars:
        raise SystemExit("No bars returned from IBKR.")
    rows = replay_intraday(symbol, bars, bar_minutes=_bar_minutes(bar_size))
    sessions = len({r["session"] for r in rows})

    print(f"\n=== {symbol} IBKR {bar_size} x {duration} — {len(rows)} bars, {sessions} sessions, cost {cost_bps:g}bps rt ===")
    print(f"    entries 10:00-14:30 ET, hard exit 15:55, no overnight, indicators reset each session")
    print(f"{'strategy':<14}{'trades':>7}{'win%':>7}{'exp%':>9}{'cum%':>9}{'maxDD%':>8}{'OOScum%':>9}{'OOStr':>7}")
    ranked = []
    for s in INTRADAY_CANDIDATES:
        m = metrics_of(rows, s, cost_bps)
        oos = walk_forward_intraday(rows, s, 0.6, cost_bps)["out_of_sample"]
        ranked.append((s.name, m, oos))
    ranked.sort(key=lambda x: x[2]["cum_return"], reverse=True)
    for name, m, oos in ranked:
        print(f"{name:<14}{m['trades']:>7}{m['win_rate']*100:>6.0f}%{m['avg_return']*100:>8.3f}%"
              f"{m['cum_return']*100:>8.2f}%{m['max_drawdown']*100:>7.1f}%{oos['cum_return']*100:>8.2f}%{oos['trades']:>7}")
    print("  ranked by out-of-sample cumulative. Intraday underlying proxy, not option P&L.")


def metrics_of(rows, strategy, cost_bps):
    from research.engine import metrics
    return metrics(simulate_intraday(rows, strategy, cost_bps))


if __name__ == "__main__":
    main()

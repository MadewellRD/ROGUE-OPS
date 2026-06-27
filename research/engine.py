#
# research/engine.py
#
# Backtest engine: replay daily bars through the real IndicatorEngine, run a
# pluggable Strategy with transaction costs, compute metrics, and split
# in-sample / out-of-sample (walk-forward). Pure given the input bars.
#
# P&L is the UNDERLYING return per trade (directional signal quality) net of a
# round-trip cost. Not option P&L — see EDGE_ROADMAP.md.
#

import datetime as dt
import statistics
from dataclasses import dataclass
from typing import Dict, List

from market.market_data import MarketSnapshot
from advisory.indicator_engine import IndicatorEngine


@dataclass
class Trade:
    entry_date: str
    entry: float
    exit_date: str
    exit: float
    ret: float
    bars_held: int
    is_open: bool


def replay(symbol: str, bars) -> List[Dict]:
    """Replay daily bars through the IndicatorEngine -> per-bar rows."""
    eng = IndicatorEngine()
    rows: List[Dict] = []
    prev_close = None
    for b in bars:
        ts = dt.datetime.fromtimestamp(b.t_ms / 1000, tz=dt.timezone.utc).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
        snap = MarketSnapshot(
            symbol=symbol, spot=b.close, session="REGULAR", timestamp_utc=ts, source="REPLAY",
            meta={"high": b.high, "low": b.low, "prev_close": prev_close, "volume": b.volume},
        )
        ind = eng.update(snap)
        rows.append({"date": b.date, "close": b.close, "req": dict(ind.required), "passed": ind.required_passed})
        prev_close = b.close
    return rows


def simulate(rows: List[Dict], strategy, cost_bps: float = 2.0) -> List[Trade]:
    """Run a strategy over rows; round-trip cost in basis points of the underlying."""
    rt = cost_bps / 10000.0
    trades: List[Trade] = []
    pos = None
    idx = 0
    for i, r in enumerate(rows):
        if pos is None:
            if strategy.entry(r["req"], r["passed"]):
                pos, idx = r, i
        elif strategy.exit(r["req"]):
            ret = (r["close"] - pos["close"]) / pos["close"] - rt
            trades.append(Trade(pos["date"], pos["close"], r["date"], r["close"], ret, i - idx, False))
            pos = None
    if pos is not None and rows:
        last = rows[-1]
        ret = (last["close"] - pos["close"]) / pos["close"] - rt
        trades.append(Trade(pos["date"], pos["close"], last["date"], last["close"], ret, len(rows) - 1 - idx, True))
    return trades


def metrics(trades: List[Trade]) -> Dict:
    n = len(trades)
    wins = sum(1 for t in trades if t.ret > 0)
    eq, peak, mdd = 1.0, 1.0, 0.0
    for t in trades:
        eq *= (1 + t.ret)
        peak = max(peak, eq)
        mdd = min(mdd, (eq - peak) / peak)
    rets = [t.ret for t in trades]
    avg = sum(rets) / n if n else 0.0
    sd = statistics.pstdev(rets) if n > 1 else 0.0
    return {
        "trades": n,
        "win_rate": (wins / n if n else 0.0),
        "avg_return": avg,                 # expectancy per trade (underlying, net cost)
        "cum_return": eq - 1.0,
        "max_drawdown": mdd,
        "sharpe_per_trade": (avg / sd if sd > 0 else 0.0),
    }


def equity_curve(trades: List[Trade]) -> List[Dict]:
    """Cumulative equity after each trade, indexed from a 1.0 base.

    Returns points the console charts directly: trade index, exit date, the
    compounding equity multiple, and that trade's net return. A leading
    (0, base) point anchors the line at 1.0 before any trade closes.
    """
    pts = [{"i": 0, "date": "", "equity": 1.0, "ret": 0.0}]
    eq = 1.0
    for i, t in enumerate(trades, start=1):
        eq *= (1 + t.ret)
        pts.append({"i": i, "date": t.exit_date, "equity": round(eq, 6), "ret": round(t.ret, 6)})
    return pts


def walk_forward(rows: List[Dict], strategy, split: float = 0.6, cost_bps: float = 2.0) -> Dict:
    """Split rows by time: in-sample (first `split`) vs out-of-sample (rest)."""
    k = int(len(rows) * split)
    return {
        "split_at": k,
        "in_sample": metrics(simulate(rows[:k], strategy, cost_bps)),
        "out_of_sample": metrics(simulate(rows[k:], strategy, cost_bps)),
    }

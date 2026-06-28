#
# capital/trade_ledger.py
#
# Paired-trade accounting + scorecard.
#
# Every CLOSED trade (an entry paired with its exit, with realized P&L) is
# appended to an append-only ledger on the shared ops volume. The scorecard
# aggregates that ledger into the measured track record — win rate, expectancy,
# equity curve, drawdown — that feeds the go-live gate.
#
# Advisory/observational: recording is best-effort and NEVER affects execution.
# The scorecard function is pure and unit-tested.
#

import datetime as dt
import json
from typing import Any, Dict, List, Optional


def _ledger_path():
    from governance.paths import ops_home
    return ops_home() / "trade_ledger.jsonl"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def record_closed_trade(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Append one closed (paired) trade. Best-effort; never raises."""
    try:
        rec = dict(row or {})
        rec.setdefault("ts_utc", _now())
        p = _ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return rec
    except Exception:
        return None


def read_ledger(limit: int = 1000) -> List[Dict[str, Any]]:
    try:
        p = _ledger_path()
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]]
    except Exception:
        return []


def _pnl(r: Dict[str, Any]) -> float:
    try:
        return float(r.get("realized_pnl_usd", 0.0))
    except (TypeError, ValueError):
        return 0.0


def scorecard(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate closed trades into a track-record scorecard. Pure.

    Equity curve is cumulative realized P&L; max drawdown is the largest
    peak-to-trough decline of that curve (in USD).
    """
    n = len(rows)
    pnls = [_pnl(r) for r in rows]
    wins = sum(1 for x in pnls if x > 0)
    losses = sum(1 for x in pnls if x < 0)
    gross = round(sum(pnls), 2)

    eq = 0.0
    peak = 0.0
    mdd = 0.0
    curve: List[Dict[str, float]] = [{"i": 0, "cum": 0.0}]
    for i, x in enumerate(pnls, start=1):
        eq += x
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
        curve.append({"i": i, "cum": round(eq, 2)})

    by_day: Dict[str, float] = {}
    for r in rows:
        d = str(r.get("closed_at_utc") or r.get("ts_utc") or "")[:10]
        by_day[d] = round(by_day.get(d, 0.0) + _pnl(r), 2)

    win_pnls = [x for x in pnls if x > 0]
    loss_pnls = [x for x in pnls if x < 0]
    return {
        "trades": n,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / n, 4) if n else None,
        "gross_pnl_usd": gross,
        "expectancy_usd": round(gross / n, 2) if n else None,
        "avg_win_usd": round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0.0,
        "avg_loss_usd": round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.0,
        "best_usd": round(max(pnls), 2) if pnls else None,
        "worst_usd": round(min(pnls), 2) if pnls else None,
        "max_drawdown_usd": round(mdd, 2),
        "equity_curve": curve,
        "by_day": by_day,
    }

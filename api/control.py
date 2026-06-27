#
# api/control.py
#
# Action surface for the operator console. The HTTP layer (terminal_server)
# stays thin and delegates here; the live loop and research harness are reused
# unchanged. Every action is defensive and returns a small JSON-able dict.
#
# Safety model:
#   - KILL is real and cross-process: it writes the durable kill file that the
#     trading loop's kill_active() honors on its next check. One direction only
#     (engage halts; clearing requires a deliberate operator action and a
#     process restart to actually resume).
#   - ARM is an INTENT flag, not a capital authorization. Flipping it writes a
#     durable marker the system can read, but live capital still passes through
#     preflight + the capital gate + the signed re-cert. Arming here is
#     necessary-not-sufficient; it can never by itself place a real-money order.
#   - RESEARCH is read-only: it runs the backtest harness and returns metrics.
#

import datetime as dt
from typing import Any, Dict, List, Optional


# ==================================================
# Durable operator flags (cross-process, under ROGUE_OPS_HOME)
# ==================================================

def _flag_path(name: str):
    from governance.paths import ops_home
    return ops_home() / name


# ---- kill ----

def engage_kill(reason: str = "operator: console kill") -> Dict[str, Any]:
    from governance.kill_switch import engage_kill as _engage, kill_context
    _engage(reason)
    return {"ok": True, "action": "kill", "kill": kill_context()}


def clear_kill() -> Dict[str, Any]:
    """Remove the durable kill file. Does NOT reset in-process kill state — a
    running trading loop stays killed until it is restarted."""
    from governance.kill_switch import clear_kill_file, kill_context
    removed = clear_kill_file()
    return {
        "ok": True,
        "action": "clear_kill",
        "file_removed": removed,
        "note": "Restart the trading process to actually resume; in-process kill is irreversible.",
        "kill": kill_context(),
    }


# ---- arm intent ----

def set_arm(armed: bool) -> Dict[str, Any]:
    p = _flag_path("ARM")
    try:
        if armed:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_now(), encoding="utf-8")
        elif p.exists():
            p.unlink()
    except Exception as e:
        return {"ok": False, "action": "arm", "error": str(e)}
    return {"ok": True, "action": "arm", "armed": arm_state()}


def arm_state() -> bool:
    try:
        return _flag_path("ARM").exists()
    except Exception:
        return False


# ==================================================
# Research (read-only backtest)
# ==================================================

def run_research(
    symbol: str = "SPY",
    days: int = 250,
    cost_bps: float = 2.0,
    source: str = "massive_daily",
    bar_size: str = "5 mins",
) -> Dict[str, Any]:
    """Run the backtest harness and return charting-ready JSON.

    source = "massive_daily"  -> daily bars from Massive, daily strategies
    source = "ibkr_intraday"  -> intraday bars from IBKR, intraday strategies
                                 (requires TWS; falls back to an error dict)
    """
    try:
        if source == "ibkr_intraday":
            return _research_intraday(symbol, days, bar_size, cost_bps)
        return _research_daily(symbol, days, cost_bps)
    except Exception as e:
        return {"ok": False, "source": source, "symbol": symbol, "error": str(e)}


def _research_daily(symbol: str, days: int, cost_bps: float) -> Dict[str, Any]:
    from market.market_data_massive import daily_bars
    from research.engine import replay, simulate, metrics, walk_forward, equity_curve
    from research.strategies import CANDIDATES

    today = dt.datetime.now(dt.timezone.utc).date()
    date_to = today.isoformat()
    date_from = (today - dt.timedelta(days=int(days) + 5)).isoformat()  # pad for non-trading days

    bars = daily_bars(symbol, date_from, date_to)
    if not bars:
        return {"ok": False, "source": "massive_daily", "symbol": symbol, "error": "no bars returned"}
    rows = replay(symbol, bars)
    price = [{"date": r["date"], "close": r["close"]} for r in rows]

    strategies = _evaluate(rows, CANDIDATES, cost_bps, simulate, metrics, walk_forward, equity_curve)
    return {
        "ok": True,
        "source": "massive_daily",
        "symbol": symbol,
        "params": {"days": int(days), "cost_bps": cost_bps, "date_from": date_from, "date_to": date_to},
        "bars": len(rows),
        "sessions": None,
        "price": price,
        "strategies": strategies,
    }


def _research_intraday(symbol: str, days: int, bar_size: str, cost_bps: float) -> Dict[str, Any]:
    from market.market_data_ibkr_history import fetch_bars
    from research.intraday import replay_intraday, simulate_intraday, walk_forward_intraday
    from research.engine import metrics, equity_curve
    from research.strategies import INTRADAY_CANDIDATES

    def _bar_minutes(bs: str) -> int:
        parts = bs.split()
        n = int(parts[0]); unit = parts[1] if len(parts) > 1 else "mins"
        return n * 60 if "hour" in unit else n

    duration = f"{int(days)} D"
    bars = fetch_bars(symbol, duration=duration, bar_size=bar_size)
    if not bars:
        return {"ok": False, "source": "ibkr_intraday", "symbol": symbol, "error": "no bars (is TWS running?)"}
    rows = replay_intraday(symbol, bars, bar_minutes=_bar_minutes(bar_size))
    price = [{"date": r.get("date") or str(i), "close": r["close"]} for i, r in enumerate(rows)]
    sessions = len({r["session"] for r in rows})

    strategies = []
    for s in INTRADAY_CANDIDATES:
        trades = simulate_intraday(rows, s, cost_bps)
        wf = walk_forward_intraday(rows, s, 0.6, cost_bps)
        strategies.append({
            "name": s.name, "note": s.note,
            "metrics": metrics(trades),
            "in_sample": wf["in_sample"], "out_of_sample": wf["out_of_sample"],
            "trades": [_trade_dict(t) for t in trades],
            "equity": equity_curve(trades),
        })
    strategies.sort(key=lambda x: x["out_of_sample"]["cum_return"], reverse=True)
    return {
        "ok": True,
        "source": "ibkr_intraday",
        "symbol": symbol,
        "params": {"days": int(days), "bar_size": bar_size, "cost_bps": cost_bps},
        "bars": len(rows),
        "sessions": sessions,
        "price": price,
        "strategies": strategies,
    }


def _evaluate(rows, candidates, cost_bps, simulate, metrics, walk_forward, equity_curve) -> List[Dict[str, Any]]:
    out = []
    for s in candidates:
        trades = simulate(rows, s, cost_bps)
        wf = walk_forward(rows, s, 0.6, cost_bps)
        out.append({
            "name": s.name, "note": s.note,
            "metrics": metrics(trades),
            "in_sample": wf["in_sample"], "out_of_sample": wf["out_of_sample"],
            "trades": [_trade_dict(t) for t in trades],
            "equity": equity_curve(trades),
        })
    out.sort(key=lambda x: x["out_of_sample"]["cum_return"], reverse=True)
    return out


def _trade_dict(t) -> Dict[str, Any]:
    return {
        "entry_date": t.entry_date, "entry": round(t.entry, 4),
        "exit_date": t.exit_date, "exit": round(t.exit, 4),
        "ret": round(t.ret, 6), "bars_held": t.bars_held, "is_open": t.is_open,
    }


# ==================================================
# Shadow LLM advisor (advisory-only, fail-soft)
# ==================================================

def ollama_status() -> Dict[str, Any]:
    from advisory import llm_ollama
    return {
        "available": llm_ollama.available(),
        "model": llm_ollama.default_model(),
        "host": llm_ollama.host(),
        "models": llm_ollama.list_models(),
    }


def shadow_now() -> Dict[str, Any]:
    """Take the latest live market frame, ask the LLM for an INDEPENDENT read,
    log it side-by-side with the deterministic signal, and return it. This never
    touches execution; it only reads the published frame and writes the ledger."""
    from api.terminal_state import get_last_frame
    from advisory import shadow_advisor, llm_ollama

    fr = get_last_frame()
    if not fr or fr.get("spot") is None:
        return {"ok": False, "error": "no live market frame yet — start the loop (main.py)",
                "available": llm_ollama.available()}
    req = fr.get("indicators") or {}
    read = shadow_advisor.shadow_read(
        fr.get("symbol", "SPY"), fr.get("spot"), fr.get("session", "REGULAR"), req, fr.get("vwap")
    )
    row = shadow_advisor.record(
        read, symbol=fr.get("symbol", "SPY"), spot=fr.get("spot"), source=fr.get("source", "LIVE"),
        det_signal=fr.get("signal_status"), det_passed=fr.get("required_passed"), req=req,
    )
    return {"ok": read.ok, "read": _asdict(read), "det_signal": fr.get("signal_status"),
            "row": row, "available": True}


def shadow_ledger(limit: int = 100) -> Dict[str, Any]:
    from advisory import shadow_advisor
    return {"ok": True, "rows": shadow_advisor.read_ledger(limit)}


def _asdict(read) -> Dict[str, Any]:
    from dataclasses import asdict
    return asdict(read)


def _now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

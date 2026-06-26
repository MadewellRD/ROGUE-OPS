#
# tools/backtest.py
#
# Daily backtest harness: replays Massive historical daily bars through the
# REAL IndicatorEngine + SignalEngine, then applies an explicit example trend
# rule to produce trade statistics over real history.
#
#   python tools\backtest.py SPY 250
#
# HONESTY NOTES:
# - SignalEngine is *presence-only* (it says a signal is ALLOWED to exist once
#   the required indicators are present); it does not encode direction. So the
#   "presence signals" count fires nearly every bar post-warmup. The actual
#   entry/exit decisions below come from EXAMPLE_RULE (trend follow on the
#   computed indicators) — clearly separated, NOT wired into live trading.
# - P&L is measured on the UNDERLYING move (directional signal quality). A real
#   0DTE option position would amplify (delta) and decay (theta) this; that
#   needs option price history, out of scope for this underlying backtest.
#

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data import MarketSnapshot
from advisory.indicator_engine import IndicatorEngine
from advisory.signal_engine import SignalEngine
from market.market_data_massive import daily_bars


# ==================================================
# Replay bars -> per-bar indicator/signal rows (pure given bars)
# ==================================================

def bars_to_rows(symbol: str, bars) -> list:
    eng = IndicatorEngine()
    sig = SignalEngine()
    rows = []
    prev_close = None
    for bar in bars:
        ts = dt.datetime.fromtimestamp(bar.t_ms / 1000, tz=dt.timezone.utc).replace(
            hour=20, minute=0, second=0, microsecond=0
        )
        snap = MarketSnapshot(
            symbol=symbol, spot=bar.close, session="REGULAR", timestamp_utc=ts, source="REPLAY",
            meta={"high": bar.high, "low": bar.low, "prev_close": prev_close, "volume": bar.volume},
        )
        ind = eng.update(snap)
        presence = sig.evaluate(snapshot=snap, indicators=ind) is not None
        rows.append({
            "date": bar.date, "close": bar.close,
            "req": dict(ind.required), "passed": ind.required_passed, "presence": presence,
        })
        prev_close = bar.close
    return rows


# ==================================================
# EXAMPLE strategy rule (trend follow) — for backtesting only
# ==================================================

def example_long_entry(req: dict, passed: bool) -> bool:
    if not passed:
        return False
    try:
        return req["EMA(9)"] > req["EMA(21)"] and req["MACD_Histogram"] > 0 and req["RSI(7)"] < 70
    except (KeyError, TypeError):
        return False


def example_exit(req: dict) -> bool:
    try:
        return req["RSI(7)"] >= 70 or req["EMA(9)"] < req["EMA(21)"]
    except (KeyError, TypeError):
        return True


# ==================================================
# Simulate + stats (pure)
# ==================================================

def simulate(rows: list) -> list:
    trades = []
    pos = None
    for r in rows:
        if pos is None:
            if example_long_entry(r["req"], r["passed"]):
                pos = {"entry_date": r["date"], "entry": r["close"]}
        elif example_exit(r["req"]):
            ret = (r["close"] - pos["entry"]) / pos["entry"]
            trades.append({**pos, "exit_date": r["date"], "exit": r["close"], "ret": ret, "open": False})
            pos = None
    if pos is not None and rows:
        last = rows[-1]
        ret = (last["close"] - pos["entry"]) / pos["entry"]
        trades.append({**pos, "exit_date": last["date"], "exit": last["close"], "ret": ret, "open": True})
    return trades


def stats(trades: list) -> dict:
    n = len(trades)
    wins = sum(1 for t in trades if t["ret"] > 0)
    eq, peak, mdd = 1.0, 1.0, 0.0
    for t in trades:
        eq *= (1 + t["ret"])
        peak = max(peak, eq)
        mdd = min(mdd, (eq - peak) / peak)
    rets = [t["ret"] for t in trades]
    return {
        "trades": n,
        "wins": wins,
        "win_rate": (wins / n if n else 0.0),
        "cum_return": eq - 1.0,
        "avg_return": (sum(rets) / n if n else 0.0),
        "max_drawdown": mdd,
    }


# ==================================================
# CLI
# ==================================================

def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 250

    to = dt.datetime.now(dt.timezone.utc).date()
    frm = to - dt.timedelta(days=int(days * 1.6) + 10)  # pad for non-trading days
    bars = daily_bars(symbol, frm.isoformat(), to.isoformat())[-days:]
    if not bars:
        raise SystemExit("No bars returned from Massive.")

    rows = bars_to_rows(symbol, bars)
    presence = sum(1 for r in rows if r["presence"])
    warm = next((i for i, r in enumerate(rows) if r["passed"]), None)
    trades = simulate(rows)
    s = stats(trades)

    print(f"\nBACKTEST {symbol} — {len(bars)} daily bars ({rows[0]['date']} .. {rows[-1]['date']})")
    print(f"  indicators warm up at bar {warm}; SignalEngine presence-signals: {presence}/{len(rows)} (presence-only)")
    print(f"\n  EXAMPLE trend rule (EMA9>EMA21 & MACD_hist>0 & RSI7<70; exit on RSI7>=70 or EMA9<EMA21):")
    print(f"    trades       {s['trades']}")
    print(f"    win rate     {s['win_rate']*100:.1f}%  ({s['wins']}/{s['trades']})")
    print(f"    avg trade    {s['avg_return']*100:+.2f}%  (underlying)")
    print(f"    cumulative   {s['cum_return']*100:+.2f}%  (underlying, compounded)")
    print(f"    max drawdown {s['max_drawdown']*100:.2f}%")
    for t in trades:
        tag = " (open)" if t["open"] else ""
        print(f"      {t['entry_date']} {t['entry']:.2f} -> {t['exit_date']} {t['exit']:.2f}  {t['ret']*100:+.2f}%{tag}")
    print("\n  NOTE: presence-only signal; example rule is a directional proxy on the underlying, not option P&L.")


if __name__ == "__main__":
    main()

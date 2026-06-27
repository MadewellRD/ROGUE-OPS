#
# tools/shadow_backtest.py
#
# Measure the shadow LLM against forward returns and the deterministic engine.
# Replays bars through the real IndicatorEngine, then for each sampled bar asks
# the local LLM for an INDEPENDENT read (it never sees the deterministic call),
# logs both to the shadow ledger, and scores them against the next bar's return.
#
# Needs Ollama running locally. LLM calls are slow, so we sample the most recent
# N bars by default.
#
#   python tools\shadow_backtest.py SPY massive_daily 120 30
#   python tools\shadow_backtest.py SPY ibkr_intraday 10 40 "5 mins"   (needs TWS)
#
# Underlying-return proxy net of nothing here — this scores DIRECTION, not option
# P&L. Small samples are noise; treat as evidence-gathering, not a verdict.
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from advisory import llm_ollama, shadow_advisor
from research.strategies import STRATEGIES


def _rows(symbol, source, days, bar_size):
    if source == "ibkr_intraday":
        from market.market_data_ibkr_history import fetch_bars
        from research.intraday import replay_intraday
        parts = bar_size.split()
        bm = (int(parts[0]) * 60) if len(parts) > 1 and "hour" in parts[1] else int(parts[0])
        bars = fetch_bars(symbol, duration=f"{int(days)} D", bar_size=bar_size)
        return replay_intraday(symbol, bars, bar_minutes=bm), True
    from market.market_data_massive import daily_bars
    from research.engine import replay
    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date()
    bars = daily_bars(symbol, (today - dt.timedelta(days=int(days) + 5)).isoformat(), today.isoformat())
    return replay(symbol, bars), False


def main() -> None:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "SPY").upper()
    source = sys.argv[2] if len(sys.argv) > 2 else "massive_daily"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    sample = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    bar_size = sys.argv[5] if len(sys.argv) > 5 else "5 mins"
    det_name = "vwap_revert" if source == "ibkr_intraday" else "trend_follow"

    if not llm_ollama.available():
        raise SystemExit(f"Ollama not reachable at {llm_ollama.host()} — start it, then retry.")

    rows, intraday = _rows(symbol, source, days, bar_size)
    if len(rows) < 3:
        raise SystemExit("not enough bars")
    det = STRATEGIES[det_name]

    # bars that have a valid forward bar (same session if intraday)
    idxs = []
    for i in range(len(rows) - 1):
        if intraday and rows[i].get("session") != rows[i + 1].get("session"):
            continue
        idxs.append(i)
    idxs = idxs[-sample:]

    print(f"\n=== {symbol} shadow vs forward returns — {source}, {len(idxs)} samples, model={llm_ollama.default_model()} ===")
    print(f"    LLM gets indicators only (NOT the engine call). Deterministic baseline = {det_name} (long-only).")

    llm_n = llm_hit = det_n = det_hit = 0
    shadow_pnl = 0.0
    for n, i in enumerate(idxs, 1):
        r, nxt = rows[i], rows[i + 1]
        fwd = (nxt["close"] - r["close"]) / r["close"] if r["close"] else 0.0
        req, passed = r["req"], r.get("passed", False)

        rd = shadow_advisor.shadow_read(symbol, r["close"], r.get("session", "REGULAR"), req, req.get("VWAP"))
        det_long = bool(det.entry(req, passed))
        shadow_advisor.record(rd, symbol=symbol, spot=r["close"], source=source,
                              det_signal=("LONG" if det_long else "FLAT"), det_passed=passed, req=req)

        if rd.bias in ("LONG", "SHORT"):
            llm_n += 1
            if (rd.bias == "LONG" and fwd > 0) or (rd.bias == "SHORT" and fwd < 0):
                llm_hit += 1
            shadow_pnl += fwd if rd.bias == "LONG" else -fwd
        if det_long:
            det_n += 1
            det_hit += 1 if fwd > 0 else 0
        print(f"  [{n}/{len(idxs)}] {r.get('date', i)} fwd={fwd*100:+.2f}%  LLM={rd.bias}({rd.confidence:.2f})  det={'LONG' if det_long else 'FLAT'}", flush=True)

    print("-" * 64)
    print(f"  LLM directional reads : {llm_n}/{len(idxs)}  hit-rate {pct(llm_hit, llm_n)}  shadow dir-PnL {shadow_pnl*100:+.2f}%")
    print(f"  Deterministic ({det_name}) : {det_n}/{len(idxs)}  hit-rate {pct(det_hit, det_n)}")
    print("  Caveat: direction only, no costs, small sample = noise. Evidence, not a verdict. Ledger appended.")


def pct(a, b):
    return f"{(a / b * 100):.0f}% ({a}/{b})" if b else "n/a"


if __name__ == "__main__":
    main()

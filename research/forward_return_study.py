#
# research/forward_return_study.py
#
# FOUNDATIONAL edge test (ROGUE-008 follow-up): before choosing DTE / structure /
# symbol, answer the only question that matters — does ANY signal predict N-day
# forward returns of an index ETF, OUT-OF-SAMPLE? Underlying-only (no options).
#
# Signals tested (pre-committed, standard — no threshold tuning):
#   - etf_mom{k}   : trailing k-day return of the ETF itself (momentum/trend)
#   - mega_mom5    : mean trailing 5-day return of the mega-cap top-10 basket
#                    (the "top-10 breadth" idea; for SPY/QQQ these ARE the top
#                     holdings, for IWM it's an external large-cap breadth read)
#   - breadth5     : fraction of the basket up over 5 days, centered at 0
#
# Metric per (symbol x signal x horizon): Pearson corr(signal_t, fwd_return_t)
# split walk-forward 60/40, IS vs OOS, plus the OOS "acting edge" = mean forward
# return when signal>0 minus the unconditional mean. An edge must hold OOS.
#
# RESEARCH ONLY. Runs against Massive daily bars (unlimited tier).
#

import sys
sys.path.insert(0, "/app")  # allow `python /tmp/forward_return_study.py` in-container

import datetime as dt
from typing import Dict, List, Optional

from market.market_data_massive import daily_bars

# Mega-cap basket — SPY & QQQ top-10 heavyweights (valid tickers). For IWM this
# is a cross-asset large-cap read (IWM's own top-10 is ~3% weight, too diffuse).
MEGA = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "AVGO", "TSLA", "COST", "NFLX"]
ETFS = ["SPY", "QQQ", "IWM"]
HORIZONS = [1, 3, 5, 7]


def _closes(symbol: str, d_from: str, d_to: str) -> Dict[str, float]:
    return {b.date: b.close for b in daily_bars(symbol, d_from, d_to)}


def pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 5:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    d = (vx * vy) ** 0.5
    return cov / d if d else 0.0


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b - 1.0


def run(days: int = 730) -> None:
    today = dt.datetime.now(dt.timezone.utc).date()
    d_from = (today - dt.timedelta(days=days)).isoformat()
    d_to = today.isoformat()

    mega = {t: _closes(t, d_from, d_to) for t in MEGA}

    print(f"Forward-return study — {d_from}..{d_to}, walk-forward 60/40 (IS|OOS)")
    print("signal      symbol  h   IS_corr  OOS_corr   OOS_acting_edge(bp)")
    verdicts = []

    for sym in ETFS:
        cl = _closes(sym, d_from, d_to)
        dates = sorted(cl)
        if len(dates) < 60:
            print(f"  {sym}: too few bars ({len(dates)})")
            continue

        # signal series aligned to dates[i]
        def etf_mom(i, k):
            return _pct(cl[dates[i]], cl[dates[i - k]]) if i >= k else None

        def mega_mom(i, k):
            vals = []
            for t in MEGA:
                m = mega[t]
                if dates[i] in m and dates[i - k] in m:
                    r = _pct(m[dates[i]], m[dates[i - k]])
                    if r is not None:
                        vals.append(r)
            return (sum(vals) / len(vals)) if vals else None

        def breadth(i, k):
            up = tot = 0
            for t in MEGA:
                m = mega[t]
                if dates[i] in m and dates[i - k] in m:
                    r = _pct(m[dates[i]], m[dates[i - k]])
                    if r is not None:
                        tot += 1
                        up += 1 if r > 0 else 0
            return (up / tot - 0.5) if tot else None

        sigfns = {"etf_mom10": lambda i: etf_mom(i, 10),
                  "mega_mom5": lambda i: mega_mom(i, 5),
                  "breadth5": lambda i: breadth(i, 5)}

        for h in HORIZONS:
            for name, fn in sigfns.items():
                pairs = []
                for i in range(len(dates) - h):
                    s = fn(i)
                    fwd = _pct(cl[dates[i + h]], cl[dates[i]])
                    if s is not None and fwd is not None:
                        pairs.append((s, fwd))
                if len(pairs) < 40:
                    continue
                cut = int(len(pairs) * 0.6)
                is_p, oos_p = pairs[:cut], pairs[cut:]
                is_c = pearson([p[0] for p in is_p], [p[1] for p in is_p])
                oos_c = pearson([p[0] for p in oos_p], [p[1] for p in oos_p])
                # OOS acting edge: mean fwd when signal>0 minus unconditional mean
                oos_all = [p[1] for p in oos_p]
                oos_sig = [p[1] for p in oos_p if p[0] > 0]
                edge_bp = None
                if oos_sig and oos_all:
                    edge_bp = (sum(oos_sig) / len(oos_sig) - sum(oos_all) / len(oos_all)) * 10000
                verdicts.append((name, sym, h, oos_c))
                print(f"  {name:<10} {sym:<6} {h:<2}  {is_c:>7.3f}  {oos_c:>7.3f}   "
                      f"{('%+.1f' % edge_bp) if edge_bp is not None else 'n/a':>8}")

    # Headline: is any signal consistently predictive OOS (|corr|>=0.10 is a weak
    # bar; a real tradable daily edge would want higher + consistent sign)?
    strong = [v for v in verdicts if abs(v[3]) >= 0.10]
    print("\nOOS |corr| >= 0.10 (weak bar):", len(strong), "of", len(verdicts), "cells")
    for v in sorted(strong, key=lambda x: -abs(x[3]))[:8]:
        print(f"   {v[0]} {v[1]} h={v[2]} OOS_corr={v[3]:+.3f}")


if __name__ == "__main__":
    run()

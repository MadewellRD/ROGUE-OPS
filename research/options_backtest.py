#
# research/options_backtest.py
#
# E1 (ROGUE-008) — option-priced 0DTE defined-risk premium backtest.
#
# Tests the only edge thesis left after directional was disproven: a NON-directional,
# defined-risk Iron Condor on SPY 0DTE, priced on REAL historical option intraday data
# from Massive (Options-Basic tier). Honest accounting INCLUDING the tail (trend days
# that breach a short strike and lose toward the wing width).
#
#   Structure (1 lot): sell ~short_pct OTM call + put, buy wings `wing` $ further out.
#   Entry ~10:00 ET (after the opening range, matching the live window).
#   Held to settlement; P&L = net credit - spread intrinsic at the underlying close.
#
# RESEARCH ONLY — not wired into live execution. The payoff core (`condor_pnl`) is pure
# and unit-tested; the data path is exercised live via `run()` in the console container.
#

import datetime as dt
import math
import time as _time
from typing import Dict, List, Optional, Tuple

from market.market_data_massive import _get, parse_aggs, intraday_bars, MassiveError
from research.intraday import _et_offset_hours


# Massive REST is rate-limited (HTTP 429). Throttle + exponential backoff so a
# multi-leg historical sweep completes instead of dropping most days.
_LAST_CALL = [0.0]


def _bt_get(path: str, tries: int = 6, min_interval: Optional[float] = None) -> Dict:
    if min_interval is None:
        import os
        # Throttle between REST calls. Default 1.0s survives the rate-limited tier;
        # set MASSIVE_MIN_INTERVAL=0.02 once on the unlimited plan for a fast sweep.
        min_interval = float(os.getenv("MASSIVE_MIN_INTERVAL", "1.0"))
    for k in range(tries):
        wait = min_interval - (_time.time() - _LAST_CALL[0])
        if wait > 0:
            _time.sleep(wait)
        _LAST_CALL[0] = _time.time()
        try:
            return _get(path)
        except MassiveError as e:
            if "429" in str(e) and k < tries - 1:
                _time.sleep(1.5 * (2 ** k))
                continue
            raise
    return {}


def _otkr(symbol: str, exp_yymmdd: str, cp: str, strike: int) -> str:
    """Polygon/Massive option ticker, e.g. O:SPY260610C00740000."""
    return f"O:{symbol}{exp_yymmdd}{cp}{int(round(strike * 1000)):08d}"


# ==================================================
# Pure payoff core (UNIT-TESTED — no IO)
# ==================================================

def condor_pnl(
    *,
    net_credit: float,
    spot_close: float,
    short_put_k: float,
    long_put_k: float,
    short_call_k: float,
    long_call_k: float,
    contracts: int = 1,
    multiplier: int = 100,
    cost_usd: float = 0.0,
) -> float:
    """Iron-condor P&L at expiry settlement, per `contracts`. Defined risk.

    Put spread loss in [0, short_put_k - long_put_k]; call spread loss in
    [0, long_call_k - short_call_k]. P&L = (credit - losses) * 100 - costs.
    """
    put_loss = max(0.0, short_put_k - spot_close) - max(0.0, long_put_k - spot_close)
    call_loss = max(0.0, spot_close - short_call_k) - max(0.0, spot_close - long_call_k)
    gross = (net_credit - put_loss - call_loss) * multiplier * contracts
    return round(gross - cost_usd, 2)


def summarize(pnls: List[float]) -> Dict:
    """Honest trade stats, tail included."""
    n = len(pnls)
    if n == 0:
        return {"n": 0, "total": 0.0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "worst": 0.0, "best": 0.0, "expectancy": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return {
        "n": n,
        "total": round(sum(pnls), 2),
        "win_rate": round(100 * len(wins) / n, 1),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "worst": round(min(pnls), 2),
        "best": round(max(pnls), 2),
        "expectancy": round(sum(pnls) / n, 2),
    }


# ==================================================
# Data path (LIVE — Massive historical option intraday)
# ==================================================

def _entry_target_ms(day: str, hour_et: int = 10, minute_et: int = 0) -> int:
    d = dt.date.fromisoformat(day)
    midnight_utc = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    off = _et_offset_hours(midnight_utc)  # EDT -4 / EST -5
    target = midnight_utc + dt.timedelta(hours=hour_et - off, minutes=minute_et)
    return int(target.timestamp() * 1000)


def _leg_price(ticker: str, day: str, target_ms: int) -> Optional[float]:
    """Option price nearest the entry time on `day` (5-min trade bar close)."""
    try:
        bars = parse_aggs(_bt_get(
            f"/v2/aggs/ticker/{ticker}/range/5/minute/{day}/{day}?adjusted=true&sort=asc&limit=5000"
        ))
    except Exception:
        return None
    if not bars:
        return None
    b = min(bars, key=lambda x: abs(x.t_ms - target_ms))
    return b.close if b.close and b.close > 0 else None


def _spy_day_map(symbol: str, date_from: str, date_to: str) -> Dict[str, Tuple[float, float]]:
    """{day: (entry_spot ~10:00, close)} from SPY 5-min RTH-ish bars."""
    bars = intraday_bars(symbol, date_from, date_to, multiplier=5, timespan="minute")
    by_day: Dict[str, List] = {}
    for b in bars:
        by_day.setdefault(b.date, []).append(b)
    out: Dict[str, Tuple[float, float]] = {}
    for day, bs in by_day.items():
        bs.sort(key=lambda x: x.t_ms)
        tgt = _entry_target_ms(day)
        entry = min(bs, key=lambda x: abs(x.t_ms - tgt)).close
        out[day] = (entry, bs[-1].close)
    return out


def _pick(chain: List[dict], kind: str, want_k: float, side: str):
    """Nearest available strike on the OTM side; returns (strike, ticker)."""
    cs = [(c.get("strike_price"), c.get("ticker")) for c in chain
          if c.get("contract_type") == kind and c.get("strike_price")]
    if not cs:
        return None
    if side == "call_short":
        cand = [x for x in cs if x[0] >= want_k] or cs
        return min(cand, key=lambda x: x[0])
    if side == "call_long":
        cand = [x for x in cs if x[0] >= want_k] or cs
        return min(cand, key=lambda x: x[0])
    if side == "put_short":
        cand = [x for x in cs if x[0] <= want_k] or cs
        return max(cand, key=lambda x: x[0])
    if side == "put_long":
        cand = [x for x in cs if x[0] <= want_k] or cs
        return max(cand, key=lambda x: x[0])
    return None


def run(symbol: str = "SPY", days: int = 45, short_pct: float = 0.004,
        wing: float = 2.0, cost_usd: float = 6.0, split: float = 0.6,
        verbose: bool = True) -> Dict:
    """Backtest a 0DTE iron condor over the last `days`. Returns IS/OOS stats."""
    today = dt.datetime.now(dt.timezone.utc).date()
    d_from = (today - dt.timedelta(days=days)).isoformat()
    d_to = today.isoformat()

    spy = _spy_day_map(symbol, d_from, d_to)
    expiries = sorted(spy.keys())
    trades: List[Tuple[str, float]] = []   # (day, pnl)
    skipped = 0

    for day in expiries:
        entry_spot, close = spy[day]

        # Construct the 4 integer-strike legs directly (no chain call → fewer
        # rate-limited requests). SPY has $1 strikes near ATM, which always exist.
        wing_i = max(1, int(round(wing)))
        sc_k = int(math.ceil(entry_spot * (1 + short_pct)))   # short call (OTM above)
        sp_k = int(math.floor(entry_spot * (1 - short_pct)))  # short put  (OTM below)
        lc_k = sc_k + wing_i                                   # long call wing
        lp_k = sp_k - wing_i                                   # long put wing
        yymmdd = dt.date.fromisoformat(day).strftime("%y%m%d")
        tgt = _entry_target_ms(day)

        psc = _leg_price(_otkr(symbol, yymmdd, "C", sc_k), day, tgt)
        plc = _leg_price(_otkr(symbol, yymmdd, "C", lc_k), day, tgt)
        psp = _leg_price(_otkr(symbol, yymmdd, "P", sp_k), day, tgt)
        plp = _leg_price(_otkr(symbol, yymmdd, "P", lp_k), day, tgt)
        if None in (psc, plc, psp, plp):
            skipped += 1
            continue

        net_credit = (psc - plc) + (psp - plp)
        if net_credit <= 0:
            skipped += 1
            continue

        pnl = condor_pnl(
            net_credit=net_credit, spot_close=close,
            short_put_k=sp_k, long_put_k=lp_k,
            short_call_k=sc_k, long_call_k=lc_k,
            cost_usd=cost_usd,
        )
        trades.append((day, pnl))

    pnls = [p for _, p in trades]
    n = len(trades)
    cut = int(n * split)
    res = {
        "symbol": symbol, "days": days, "expiries_traded": n, "skipped": skipped,
        "params": {"short_pct": short_pct, "wing": wing, "cost_usd": cost_usd},
        "all": summarize(pnls),
        "in_sample": summarize(pnls[:cut]),
        "out_of_sample": summarize(pnls[cut:]),
        "worst_days": sorted(trades, key=lambda x: x[1])[:5],
    }
    if verbose:
        import json
        print(json.dumps(res, indent=2, default=str))
    return res


if __name__ == "__main__":
    run()

#
# research/intraday.py
#
# Intraday-faithful backtest, modeling what the live 0DTE system actually does:
#   - indicators RESET each session (no carry-over across days)
#   - entries only inside the live window (after the 30-min opening range,
#     up to the 14:30 ET cutoff)
#   - hard exit by 15:55 ET; NO overnight holds (0DTE)
#   - intraday features (session VWAP distance, opening-range break) exposed in
#     `req` so stateless strategies can use them.
#
# Timezone-free: bars are RTH-filtered (useRTH=1), so session structure and
# minutes-since-open are derived from the bar sequence — no tzdata dependency.
#

import datetime as dt
from typing import Dict, List

from market.market_data import MarketSnapshot
from advisory.indicator_engine import IndicatorEngine
from research.engine import Trade, metrics


def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    first = dt.date(year, month, 1)
    first_sun = first + dt.timedelta(days=(6 - first.weekday()) % 7)
    return first_sun + dt.timedelta(days=7 * (n - 1))


def _et_offset_hours(when_utc: dt.datetime) -> int:
    """US-Eastern UTC offset with DST (EDT -4 from 2nd Sun Mar to 1st Sun Nov,
    else EST -5). Dependency-free (no tzdata); date-granular at the ~2 DST
    boundary days, which is immaterial for an RTH session filter."""
    d = when_utc.date()
    return -4 if (_nth_sunday(when_utc.year, 3, 2) <= d < _nth_sunday(when_utc.year, 11, 1)) else -5


def keep_rth(bars: List) -> List:
    """Keep regular-session bars (09:30-15:59 ET, weekdays). Vendor intraday
    aggregates (e.g. Massive) include pre/post-market, which would corrupt the
    session/entry-window logic that assumes each session starts at the open."""
    out = []
    for b in bars:
        u = dt.datetime.fromtimestamp(b.t_ms / 1000, tz=dt.timezone.utc)
        et = u + dt.timedelta(hours=_et_offset_hours(u))
        if et.weekday() < 5:
            mins = et.hour * 60 + et.minute
            if 9 * 60 + 30 <= mins < 16 * 60:
                out.append(b)
    return out

OPENING_RANGE_MIN = 30      # first 30 minutes define the opening range
ENTRY_START_MIN = 30        # 10:00 ET (after the opening range)
ENTRY_END_MIN = 300         # 14:30 ET (live entry cutoff)
HARD_EXIT_MIN = 385         # 15:55 ET
SESSION_GAP_MIN = 120       # gap > 2h between bars => new session


def _epoch_to_utc(t_ms):
    import datetime as dt
    return dt.datetime.fromtimestamp(t_ms / 1000, tz=dt.timezone.utc)


def replay_intraday(symbol: str, bars, bar_minutes: int = 5) -> List[Dict]:
    rows: List[Dict] = []
    eng = None
    prev_t = None
    prev_close = None
    idx_in_session = 0
    session = -1
    or_high = or_low = None

    for b in bars:
        gap = None if prev_t is None else (b.t_ms - prev_t) / 60000.0
        if prev_t is None or gap is None or gap > SESSION_GAP_MIN:
            session += 1
            idx_in_session = 0
            eng = IndicatorEngine()
            prev_close = None
            or_high = or_low = None
        else:
            idx_in_session += 1
        mins = idx_in_session * bar_minutes

        snap = MarketSnapshot(
            symbol=symbol, spot=b.close, session="REGULAR",
            timestamp_utc=_epoch_to_utc(b.t_ms), source="REPLAY",
            meta={"high": b.high, "low": b.low, "prev_close": prev_close, "volume": b.volume},
        )
        ind = eng.update(snap)
        req = dict(ind.required)

        if mins < OPENING_RANGE_MIN:
            or_high = b.high if or_high is None else max(or_high, b.high)
            or_low = b.low if or_low is None else min(or_low, b.low)

        vwap = (ind.advisory or {}).get("VWAP")
        req["VWAP"] = vwap
        req["VWAP_dist"] = ((b.close - vwap) / vwap) if vwap else None
        req["OR_high"] = or_high
        req["OR_low"] = or_low
        req["above_OR"] = bool(or_high is not None and mins >= ENTRY_START_MIN and b.close > or_high)
        req["mins"] = mins

        rows.append({
            "i": len(rows), "session": session, "close": b.close, "req": req,
            "passed": ind.required_passed,
            "in_window": ENTRY_START_MIN <= mins <= ENTRY_END_MIN,
            "hard_exit": mins >= HARD_EXIT_MIN,
        })
        prev_t = b.t_ms
        prev_close = b.close
    return rows


def simulate_intraday(rows: List[Dict], strategy, cost_bps: float = 1.0) -> List[Trade]:
    rt = cost_bps / 10000.0
    trades: List[Trade] = []
    pos = None
    for r in rows:
        if pos is not None:
            if r["session"] != pos["session"] or r["hard_exit"] or strategy.exit(r["req"]):
                ret = (r["close"] - pos["close"]) / pos["close"] - rt
                trades.append(Trade(str(pos["i"]), pos["close"], str(r["i"]), r["close"], ret, r["i"] - pos["i"], False))
                pos = None
        if pos is None and r["in_window"] and not r["hard_exit"] and strategy.entry(r["req"], r["passed"]):
            pos = r
    if pos is not None and rows:
        last = rows[-1]
        ret = (last["close"] - pos["close"]) / pos["close"] - rt
        trades.append(Trade(str(pos["i"]), pos["close"], str(last["i"]), last["close"], ret, last["i"] - pos["i"], True))
    return trades


def walk_forward_intraday(rows: List[Dict], strategy, split: float = 0.6, cost_bps: float = 1.0) -> Dict:
    sessions = sorted({r["session"] for r in rows})
    if not sessions:
        return {"in_sample": metrics([]), "out_of_sample": metrics([])}
    cut = sessions[min(int(len(sessions) * split), len(sessions) - 1)]
    is_rows = [r for r in rows if r["session"] < cut]
    oos_rows = [r for r in rows if r["session"] >= cut]
    return {
        "sessions": len(sessions),
        "in_sample": metrics(simulate_intraday(is_rows, strategy, cost_bps)),
        "out_of_sample": metrics(simulate_intraday(oos_rows, strategy, cost_bps)),
    }

#
# research/strategies.py
#
# Pluggable, value-based candidate strategies for the backtest harness.
# Each reads the computed indicator dict (req) + the required_passed flag and
# returns entry/exit booleans. All are fail-closed: missing/None indicators
# mean "do not enter" and "exit". RESEARCH ONLY — not wired into live trading.
#

from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class Strategy:
    name: str
    entry: Callable[[Dict, bool], bool]
    exit: Callable[[Dict], bool]
    note: str = ""


def _num(req: Dict, key: str):
    v = req.get(key)
    return v if isinstance(v, (int, float)) else None


# ---- trend_follow ----
def _trend_entry(req, passed):
    if not passed:
        return False
    e9, e21, m, r = _num(req, "EMA(9)"), _num(req, "EMA(21)"), _num(req, "MACD_Histogram"), _num(req, "RSI(7)")
    if None in (e9, e21, m, r):
        return False
    return e9 > e21 and m > 0 and r < 70


def _trend_exit(req):
    e9, e21, r = _num(req, "EMA(9)"), _num(req, "EMA(21)"), _num(req, "RSI(7)")
    if None in (e9, e21, r):
        return True
    return r >= 70 or e9 < e21


# ---- macd_momentum ----
def _macd_entry(req, passed):
    if not passed:
        return False
    m, r = _num(req, "MACD_Histogram"), _num(req, "RSI(14)")
    if None in (m, r):
        return False
    return m > 0 and 45 <= r < 70


def _macd_exit(req):
    m = _num(req, "MACD_Histogram")
    return True if m is None else m < 0


# ---- rsi_meanrev (long oversold bounce, trend-filtered) ----
def _rsi_entry(req, passed):
    if not passed:
        return False
    r7, e9, e21 = _num(req, "RSI(7)"), _num(req, "EMA(9)"), _num(req, "EMA(21)")
    if None in (r7, e9, e21):
        return False
    return r7 < 30 and e9 >= e21          # oversold within an up/neutral trend


def _rsi_exit(req):
    r7 = _num(req, "RSI(7)")
    return True if r7 is None else r7 >= 55


# ---- ema_cross (pure trend regime) ----
def _cross_entry(req, passed):
    if not passed:
        return False
    e9, e21 = _num(req, "EMA(9)"), _num(req, "EMA(21)")
    if None in (e9, e21):
        return False
    return e9 > e21


def _cross_exit(req):
    e9, e21 = _num(req, "EMA(9)"), _num(req, "EMA(21)")
    if None in (e9, e21):
        return True
    return e9 < e21


CANDIDATES: List[Strategy] = [
    Strategy("trend_follow", _trend_entry, _trend_exit, "EMA9>EMA21 & MACD_hist>0 & RSI7<70; exit RSI7>=70 or EMA9<EMA21"),
    Strategy("macd_momentum", _macd_entry, _macd_exit, "MACD_hist>0 & 45<=RSI14<70; exit MACD_hist<0"),
    Strategy("rsi_meanrev", _rsi_entry, _rsi_exit, "RSI7<30 & EMA9>=EMA21; exit RSI7>=55"),
    Strategy("ema_cross", _cross_entry, _cross_exit, "EMA9>EMA21; exit EMA9<EMA21"),
]

STRATEGIES: Dict[str, Strategy] = {s.name: s for s in CANDIDATES}

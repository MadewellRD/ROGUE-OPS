#
# tools/test_shadow_eval.py
#
# Offline, deterministic tests for the shadow ledger scorer (no network):
#   - pairing respects symbol boundaries and the max-gap window (overnight skip),
#   - hit-rate / coverage / dir-PnL / agreement math is correct on a hand-built
#     ledger with known forward moves,
#   - FLAT/UNKNOWN reads are excluded from directional coverage.
#
#   python tools\test_shadow_eval.py
#

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.shadow_eval import pair_forward, score

BASE = 1_700_000_000


def _ts(offset_sec):
    return dt.datetime.fromtimestamp(BASE + offset_sec, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _row(off, symbol, spot, bias, conf, det):
    return {"ts_utc": _ts(off), "symbol": symbol, "spot": spot, "det_signal": det,
            "det_passed": det in ("ENTRY", "HOLD"),
            "llm": {"bias": bias, "confidence": conf, "model": "mock"}}


def test_pairing_rules():
    # same symbol within window -> pair; symbol change -> skip; >30min -> skip
    rows = [
        _row(0, "SPY", 100.0, "LONG", 0.8, "HOLD"),
        _row(60, "SPY", 101.0, "SHORT", 0.7, "NO_SIGNAL"),
        _row(120, "IWM", 200.0, "LONG", 0.9, "ENTRY"),   # symbol change at 60->120? no: 60(SPY)->120(IWM) skip
        _row(7320, "SPY", 105.0, "LONG", 0.9, "ENTRY"),  # 2h after -> gap too large
    ]
    pairs = pair_forward(rows, max_gap_sec=1800)
    # only SPY t0->t1 qualifies
    assert len(pairs) == 1, [p[0]["ts_utc"] for p in pairs]
    assert pairs[0][0]["llm"]["bias"] == "LONG"
    assert abs(pairs[0][1] - 0.01) < 1e-9


def test_score_math():
    rows = [
        _row(0,   "SPY", 100.0,  "LONG",  0.8, "HOLD"),       # ->101.0  +1.00%  LLM LONG hit ; det long hit
        _row(60,  "SPY", 101.0,  "SHORT", 0.7, "NO_SIGNAL"),  # ->100.0  -0.99%  LLM SHORT hit; det not long
        _row(120, "SPY", 100.0,  "FLAT",  0.0, "HOLD"),       # ->100.5  +0.50%  LLM flat(excl); det long hit
        _row(180, "SPY", 100.5,  "LONG",  0.5, "ENTRY"),      # ->100.0  -0.50%  LLM LONG miss; det long miss
        _row(240, "SPY", 100.0,  "FLAT",  0.0, "NO_SIGNAL"),  # last paired target
    ]
    m = score(rows, max_gap_sec=1800)
    assert m["paired"] == 4, m
    llm = m["llm"]
    assert llm["directional"] == 3 and llm["hits"] == 2
    assert llm["hit_rate"] == round(2 / 3, 4)
    assert llm["coverage"] == 0.75
    assert abs(llm["dir_pnl_pct"] - 1.493) < 0.01, llm["dir_pnl_pct"]
    assert llm["high_conf_n"] == 2 and llm["high_conf_hit_rate"] == 1.0   # 0.8 & 0.7 both hit
    det = m["deterministic"]
    assert det["directional"] == 3 and det["hits"] == 2
    assert m["agreement_rate"] == 0.5


def test_empty():
    m = score([], max_gap_sec=1800)
    assert m["paired"] == 0 and m["llm"]["hit_rate"] is None


def main() -> None:
    test_pairing_rules()
    test_score_math()
    test_empty()
    print("SHADOW EVAL PASS — pairing (symbol/gap), hit-rate/coverage/dir-PnL/agreement math, empty-safe")


if __name__ == "__main__":
    main()

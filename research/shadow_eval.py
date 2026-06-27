#
# research/shadow_eval.py
#
# Score the shadow ledger against what the market actually did next.
#
# Each ledger row is one read at a point in time. We pair consecutive rows of
# the same symbol (skipping gaps too large to be one session, e.g. the loop was
# stopped) and treat the next row's spot as the realized forward move. Then we
# ask the only question that matters: did the LLM's INDEPENDENT bias line up with
# that move more often than chance — and than the deterministic engine?
#
# Pure and offline. Direction only, interval-to-interval, no costs — evidence to
# accumulate, never a standalone verdict. Small samples are noise.
#

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

_LONGISH_DET = {"ENTRY", "HOLD"}          # the engine being/staying in a long-call posture
_DIRECTIONAL = {"LONG", "SHORT"}


def _epoch(ts: str) -> Optional[float]:
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def pair_forward(rows: List[Dict[str, Any]], max_gap_sec: float = 1800.0) -> List[Tuple[Dict[str, Any], float, float]]:
    """Pair each row with the next same-symbol row within max_gap_sec.
    Returns (row, forward_return, gap_sec). Forward return is fractional."""
    out: List[Tuple[Dict[str, Any], float, float]] = []
    s = [r for r in rows if isinstance(r, dict)]
    s.sort(key=lambda r: _epoch(r.get("ts_utc")) or 0.0)
    for a, b in zip(s, s[1:]):
        if a.get("symbol") != b.get("symbol"):
            continue
        ta, tb = _epoch(a.get("ts_utc")), _epoch(b.get("ts_utc"))
        if ta is None or tb is None:
            continue
        gap = tb - ta
        if gap <= 0 or gap > max_gap_sec:
            continue
        pa, pb = a.get("spot"), b.get("spot")
        if not isinstance(pa, (int, float)) or not isinstance(pb, (int, float)) or pa == 0:
            continue
        out.append((a, (pb - pa) / pa, gap))
    return out


def _bias(row: Dict[str, Any]) -> str:
    return str((row.get("llm") or {}).get("bias", "")).upper()


def _conf(row: Dict[str, Any]) -> float:
    try:
        return float((row.get("llm") or {}).get("confidence", 0.0))
    except Exception:
        return 0.0


def score(rows: List[Dict[str, Any]], max_gap_sec: float = 1800.0) -> Dict[str, Any]:
    pairs = pair_forward(rows, max_gap_sec)
    llm_n = llm_hit = det_n = det_hit = agree = 0
    llm_pnl = 0.0
    hi_n = hi_hit = 0
    models = set()

    for row, fwd, _gap in pairs:
        b = _bias(row)
        models.add((row.get("llm") or {}).get("model"))
        det_long = str(row.get("det_signal", "")).upper() in _LONGISH_DET

        llm_act = b in _DIRECTIONAL
        if llm_act:
            llm_n += 1
            hit = (b == "LONG" and fwd > 0) or (b == "SHORT" and fwd < 0)
            llm_hit += 1 if hit else 0
            llm_pnl += fwd if b == "LONG" else -fwd
            if _conf(row) >= 0.66:
                hi_n += 1
                hi_hit += 1 if hit else 0
        if det_long:
            det_n += 1
            det_hit += 1 if fwd > 0 else 0
        if llm_act == det_long:
            agree += 1

    paired = len(pairs)
    return {
        "rows": len(rows),
        "paired": paired,
        "max_gap_sec": max_gap_sec,
        "models": sorted(m for m in models if m),
        "llm": {
            "directional": llm_n,
            "coverage": _rate(llm_n, paired),
            "hits": llm_hit,
            "hit_rate": _rate(llm_hit, llm_n),
            "dir_pnl_pct": round(llm_pnl * 100, 3),
            "high_conf_n": hi_n,
            "high_conf_hit_rate": _rate(hi_hit, hi_n),
        },
        "deterministic": {
            "directional": det_n,
            "hits": det_hit,
            "hit_rate": _rate(det_hit, det_n),
        },
        "agreement_rate": _rate(agree, paired),
    }


def _rate(a: int, b: int) -> Optional[float]:
    return round(a / b, 4) if b else None


def format_report(m: Dict[str, Any]) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x * 100:.0f}%"
    llm, det = m["llm"], m["deterministic"]
    lines = [
        f"  ledger rows         : {m['rows']}   paired (<= {m['max_gap_sec']:.0f}s gap): {m['paired']}",
        f"  model(s)            : {', '.join(m['models']) or 'n/a'}",
        f"  LLM directional     : {llm['directional']}/{m['paired']}  (coverage {pct(llm['coverage'])})",
        f"  LLM hit-rate        : {pct(llm['hit_rate'])}   high-conf(>=0.66) {pct(llm['high_conf_hit_rate'])} on {llm['high_conf_n']}",
        f"  LLM dir-PnL proxy   : {llm['dir_pnl_pct']:+.2f}%   (direction only, no costs)",
        f"  Deterministic hit   : {pct(det['hit_rate'])} on {det['directional']}",
        f"  Agree w/ engine     : {pct(m['agreement_rate'])}",
        "  Caveat: interval-to-interval direction, small samples = noise. Evidence, not a verdict.",
    ]
    return "\n".join(lines)

#
# advisory/shadow_advisor.py
#
# SHADOW signal advisor.
#
# Each call asks a local LLM for an INDEPENDENT read of the tape and logs it
# side-by-side with the deterministic engine's decision. Two hard rules:
#
#   1. The prompt DELIBERATELY withholds the deterministic engine's signal, so
#      we measure the LLM's independent skill, not its ability to parrot.
#   2. The output is LOGGED ONLY. It is never returned to, consulted by, or
#      importable from the execution path. It cannot place, size, or block a
#      trade. Fail-soft throughout (Ollama down -> ok=False, never an exception).
#
# The point is to accumulate an honest ledger so we can later ask: would this
# read have added edge? — the same evidence-before-capital discipline we apply
# to every other signal in ROGUE:OPS.
#

import datetime as dt
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from advisory import llm_ollama

SYSTEM = (
    "You are a shadow market-structure analyst for SPY/IWM intraday options. "
    "You ONLY observe; your output is logged for later evaluation and is NEVER "
    "used to place trades. Given the current price and indicator values, return "
    'STRICT JSON: {"bias":"LONG"|"SHORT"|"FLAT","confidence":<number 0..1>,'
    '"rationale":"<=160 chars"}. Use only the values provided. If the signals '
    "conflict or are weak, prefer FLAT."
)

_VALID = {"LONG", "SHORT", "FLAT"}
_LEDGER_KEYS = ("VWAP_Position", "EMA(9)", "EMA(21)", "RSI(7)", "RSI(14)", "MACD_Histogram", "ATR")


@dataclass
class ShadowRead:
    ok: bool
    bias: str            # LONG | SHORT | FLAT | UNKNOWN
    confidence: float
    rationale: str
    model: str
    latency_ms: int


def _fmt(v, d: int = 2) -> str:
    return f"{v:.{d}f}" if isinstance(v, (int, float)) else "n/a"


def build_prompt(symbol: str, spot, session: str, req: Dict[str, Any], vwap=None) -> str:
    """Render the frame for the LLM. NOTE: never includes the deterministic
    engine's signal — independence is the whole point."""
    g = req.get
    return (
        f"{symbol} spot={_fmt(spot)} session={session}\n"
        f"VWAP={_fmt(vwap)} VWAP_Position={g('VWAP_Position')} ATR={_fmt(g('ATR'))}\n"
        f"EMA9={_fmt(g('EMA(9)'))} EMA21={_fmt(g('EMA(21)'))}\n"
        f"RSI7={_fmt(g('RSI(7)'), 1)} RSI14={_fmt(g('RSI(14)'), 1)} MACD_hist={_fmt(g('MACD_Histogram'), 3)}\n"
        "Return the JSON read."
    )


def shadow_read(symbol: str, spot, session: str, req: Dict[str, Any], vwap=None,
                *, model: Optional[str] = None, timeout: float = 30.0) -> ShadowRead:
    m = model or llm_ollama.default_model()
    t0 = time.time()
    obj = llm_ollama.generate_json(
        build_prompt(symbol, spot, session, req, vwap), system=SYSTEM, model=m, timeout=timeout
    )
    latency = int((time.time() - t0) * 1000)
    if not obj:
        return ShadowRead(False, "UNKNOWN", 0.0, "ollama unavailable or unparseable", m, latency)
    bias = str(obj.get("bias", "")).upper().strip()
    if bias not in _VALID:
        bias = "FLAT"
    try:
        conf = max(0.0, min(1.0, float(obj.get("confidence", 0.0))))
    except Exception:
        conf = 0.0
    return ShadowRead(True, bias, conf, str(obj.get("rationale", ""))[:200], m, latency)


# ==================================================
# Ledger (append-only JSONL under ROGUE_OPS_HOME)
# ==================================================

def _ledger_path():
    from governance.paths import ops_home
    return ops_home() / "shadow_ledger.jsonl"


def record(read: ShadowRead, *, symbol: str, spot, source: str,
           det_signal, det_passed, req: Dict[str, Any]) -> Dict[str, Any]:
    """Append one side-by-side row. Returns the row (also for live display)."""
    row = {
        "ts_utc": _now(),
        "symbol": symbol,
        "spot": spot,
        "source": source,
        "det_signal": det_signal,        # the deterministic engine's call
        "det_passed": det_passed,
        "llm": {
            "bias": read.bias, "confidence": read.confidence, "rationale": read.rationale,
            "ok": read.ok, "model": read.model, "latency_ms": read.latency_ms,
        },
        "indicators": {k: req.get(k) for k in _LEDGER_KEYS},
    }
    try:
        p = _ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass  # ledger is best-effort; never breaks the caller
    return row


def read_ledger(limit: int = 200) -> List[Dict[str, Any]]:
    try:
        p = _ledger_path()
        if not p.exists():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]]
    except Exception:
        return []


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

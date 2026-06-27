#
# advisory/shadow_runner.py
#
# OPTIONAL, OFF-BY-DEFAULT bridge that lets the live loop fire SHADOW reads
# automatically so the ledger fills during SIM/paper runs.
#
# Engineered so it can NEVER affect the trading loop:
#   - disabled unless OLLAMA_SHADOW is truthy,
#   - the LLM call + ledger write run on a DAEMON THREAD (zero added latency),
#   - throttled (OLLAMA_SHADOW_INTERVAL_SEC, default 60s) with single-flight, so
#     a slow local model can never pile up or back-pressure the loop,
#   - every path is wrapped; it returns a Thread handle (for tests) or None and
#     never raises into the caller.
#
# Same contract as the rest of the shadow layer: logged only, never consulted by
# the execution path.
#

import os
import threading
import time
from typing import Any, Dict, Optional

from advisory import shadow_advisor

_lock = threading.Lock()
_last_fire = 0.0
_busy = False


def enabled() -> bool:
    return os.getenv("OLLAMA_SHADOW", "").strip().lower() in ("1", "true", "yes", "on")


def interval_sec() -> float:
    try:
        return max(0.0, float(os.getenv("OLLAMA_SHADOW_INTERVAL_SEC", "60")))
    except Exception:
        return 60.0


def maybe_shadow(*, symbol, spot, session, req: Dict[str, Any], vwap=None,
                 det_signal=None, det_passed=None, model=None) -> Optional[threading.Thread]:
    """If enabled and neither throttled nor already running, fire a background
    shadow read + ledger append. Returns the Thread (tests may join) or None.
    Never blocks the caller; never raises."""
    global _last_fire, _busy
    try:
        if not enabled() or spot is None:
            return None
        now = time.time()
        with _lock:
            if _busy or (now - _last_fire) < interval_sec():
                return None
            _last_fire = now
            _busy = True
    except Exception:
        return None

    def _work():
        global _busy
        try:
            rd = shadow_advisor.shadow_read(symbol, spot, session, req or {}, vwap, model=model)
            shadow_advisor.record(
                rd, symbol=symbol, spot=spot, source="LIVE",
                det_signal=det_signal, det_passed=det_passed, req=req or {},
            )
            try:
                from api.terminal_state import publish_shadow
                publish_shadow({
                    "bias": rd.bias, "confidence": rd.confidence, "rationale": rd.rationale,
                    "ok": rd.ok, "model": rd.model, "latency_ms": rd.latency_ms,
                    "det_signal": det_signal,
                })
            except Exception:
                pass
        except Exception:
            pass  # a shadow read can never surface an error into the system
        finally:
            with _lock:
                _busy = False

    try:
        t = threading.Thread(target=_work, name="shadow-read", daemon=True)
        t.start()
        return t
    except Exception:
        with _lock:
            _busy = False
        return None


def _reset_for_test() -> None:
    """Reset throttle/single-flight state (tests only)."""
    global _last_fire, _busy
    with _lock:
        _last_fire = 0.0
        _busy = False

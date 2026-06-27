#
# tools/test_shadow_runner.py
#
# Offline tests for the optional live-loop shadow bridge (no real model):
#   - OFF by default (no OLLAMA_SHADOW -> no-op, returns None),
#   - when enabled: fires a background read, appends the ledger, publishes state,
#   - throttled (second call within the interval is skipped),
#   - single-flight (no second thread while one is running),
#   - FAIL-SOFT (a raising read never propagates; busy state resets).
#
#   python tools\test_shadow_runner.py
#

import os
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ["ROGUE_OPS_HOME"] = tempfile.mkdtemp(prefix="rogue_shadowrun_test_")

from advisory import shadow_advisor, shadow_runner

REQ = {"VWAP_Position": "above", "EMA(9)": 601.2, "EMA(21)": 600.8,
       "RSI(7)": 63.4, "RSI(14)": 55.2, "MACD_Histogram": 0.18, "ATR": 1.32}


def _canned(*a, **k):
    return shadow_advisor.ShadowRead(True, "LONG", 0.7, "trend up", "mock", 5)


def _fire():
    return shadow_runner.maybe_shadow(symbol="SPY", spot=601.3, session="REGULAR",
                                      req=REQ, vwap=600.95, det_signal="HOLD", det_passed=True)


def test_off_by_default():
    os.environ.pop("OLLAMA_SHADOW", None)
    shadow_runner._reset_for_test()
    orig = shadow_advisor.shadow_read
    shadow_advisor.shadow_read = _canned
    try:
        assert _fire() is None, "must be a no-op unless OLLAMA_SHADOW is enabled"
    finally:
        shadow_advisor.shadow_read = orig


def test_enabled_fires_logs_and_publishes():
    from api import terminal_state
    os.environ["OLLAMA_SHADOW"] = "1"
    os.environ["OLLAMA_SHADOW_INTERVAL_SEC"] = "0"
    shadow_runner._reset_for_test()
    orig = shadow_advisor.shadow_read
    shadow_advisor.shadow_read = _canned
    try:
        before = len(shadow_advisor.read_ledger(1000))
        t = _fire()
        assert t is not None
        t.join(timeout=5)
        after = len(shadow_advisor.read_ledger(1000))
        assert after == before + 1, "enabled run must append exactly one ledger row"
        assert shadow_advisor.read_ledger(1)[-1]["llm"]["bias"] == "LONG"
        assert terminal_state._LAST_SHADOW.get("bias") == "LONG", "must publish to terminal state"
    finally:
        shadow_advisor.shadow_read = orig


def test_throttle():
    os.environ["OLLAMA_SHADOW"] = "1"
    os.environ["OLLAMA_SHADOW_INTERVAL_SEC"] = "60"
    shadow_runner._reset_for_test()
    orig = shadow_advisor.shadow_read
    shadow_advisor.shadow_read = _canned
    try:
        t1 = _fire()
        assert t1 is not None
        t1.join(timeout=5)
        assert _fire() is None, "a second call within the interval must be throttled"
    finally:
        shadow_advisor.shadow_read = orig


def test_single_flight():
    os.environ["OLLAMA_SHADOW"] = "1"
    os.environ["OLLAMA_SHADOW_INTERVAL_SEC"] = "0"
    shadow_runner._reset_for_test()
    gate = threading.Event()
    orig = shadow_advisor.shadow_read

    def _blocking(*a, **k):
        gate.wait(timeout=5)
        return _canned()

    shadow_advisor.shadow_read = _blocking
    try:
        t1 = _fire()
        assert t1 is not None, "first call should fire"
        assert _fire() is None, "no second thread while one is in flight"
        gate.set()
        t1.join(timeout=5)
        t3 = _fire()
        assert t3 is not None, "after completion, firing is allowed again"
        t3.join(timeout=5)
    finally:
        gate.set()
        shadow_advisor.shadow_read = orig


def test_fail_soft():
    os.environ["OLLAMA_SHADOW"] = "1"
    os.environ["OLLAMA_SHADOW_INTERVAL_SEC"] = "0"
    shadow_runner._reset_for_test()
    orig = shadow_advisor.shadow_read

    def _boom(*a, **k):
        raise RuntimeError("model exploded")

    shadow_advisor.shadow_read = _boom
    try:
        t = _fire()
        assert t is not None
        t.join(timeout=5)  # the raising read is swallowed inside the thread
        shadow_advisor.shadow_read = _canned
        assert _fire() is not None, "busy state must reset after a failed read"
    finally:
        shadow_advisor.shadow_read = orig


def main() -> None:
    test_off_by_default()
    test_enabled_fires_logs_and_publishes()
    test_throttle()
    test_single_flight()
    test_fail_soft()
    print("SHADOW RUNNER PASS — off-by-default, fires+logs+publishes, throttle, single-flight, fail-soft")


if __name__ == "__main__":
    main()

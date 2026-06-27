#
# tools/test_shadow.py
#
# Offline, deterministic tests for the shadow LLM advisor (no real model):
#   - response parsing (bias normalize, confidence clamp, invalid -> FLAT),
#   - FAIL-SOFT when Ollama is unreachable (ok=False, never raises),
#   - the prompt WITHHOLDS the deterministic engine's call (independence),
#   - ledger append + read round-trip,
#   - a real urllib round-trip against a mock Ollama on loopback,
#   - a mechanical guard: execution/ and capital/ never import the LLM layer.
#
#   python tools\test_shadow.py
#

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ["ROGUE_OPS_HOME"] = tempfile.mkdtemp(prefix="rogue_shadow_test_")

from advisory import llm_ollama, shadow_advisor

REQ = {
    "VWAP_Position": "above", "EMA(9)": 601.2, "EMA(21)": 600.8,
    "RSI(7)": 63.4, "RSI(14)": 55.2, "MACD_Histogram": 0.18, "ATR": 1.32,
}


def test_parsing_and_clamp():
    orig = llm_ollama.generate
    llm_ollama.generate = lambda *a, **k: '{"bias":"long","confidence":1.7,"rationale":"trend up"}'
    try:
        rd = shadow_advisor.shadow_read("SPY", 601.3, "REGULAR", REQ, 600.95)
    finally:
        llm_ollama.generate = orig
    assert rd.ok and rd.bias == "LONG", rd
    assert rd.confidence == 1.0, "confidence must clamp to [0,1]"
    assert rd.rationale == "trend up"


def test_invalid_bias_becomes_flat():
    orig = llm_ollama.generate
    llm_ollama.generate = lambda *a, **k: '{"bias":"sideways","confidence":0.3}'
    try:
        rd = shadow_advisor.shadow_read("SPY", 601.3, "REGULAR", REQ)
    finally:
        llm_ollama.generate = orig
    assert rd.ok and rd.bias == "FLAT", rd


def test_fail_soft_when_down():
    orig = llm_ollama.generate
    llm_ollama.generate = lambda *a, **k: None
    try:
        rd = shadow_advisor.shadow_read("SPY", 601.3, "REGULAR", REQ)
    finally:
        llm_ollama.generate = orig
    assert rd.ok is False and rd.bias == "UNKNOWN", "must fail soft, never raise"


def test_prompt_withholds_deterministic_call():
    p = shadow_advisor.build_prompt("SPY", 601.3, "REGULAR", REQ, 600.95).lower()
    assert "rsi7" in p and "macd_hist" in p, "indicators must be present"
    for leak in ("signal", "deterministic", "entry", "hold", "engine"):
        assert leak not in p, f"prompt must NOT leak the deterministic call (found '{leak}')"


def test_ledger_round_trip():
    rd = shadow_advisor.ShadowRead(True, "SHORT", 0.6, "vwap reject", "llama3.2", 120)
    row = shadow_advisor.record(rd, symbol="SPY", spot=601.3, source="TEST",
                                det_signal="HOLD", det_passed=True, req=REQ)
    assert row["llm"]["bias"] == "SHORT"
    rows = shadow_advisor.read_ledger(10)
    assert rows and rows[-1]["llm"]["bias"] == "SHORT" and rows[-1]["det_signal"] == "HOLD"


def test_http_round_trip_against_mock_ollama():
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            self._send({"models": [{"name": "llama3.2"}]})
        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(n)
            self._send({"response": '{"bias":"SHORT","confidence":0.6,"rationale":"vwap reject"}'})
        def _send(self, obj):
            b = json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert llm_ollama.available() is True
        assert "llama3.2" in llm_ollama.list_models()
        rd = shadow_advisor.shadow_read("SPY", 601.3, "REGULAR", REQ, 600.95)
        assert rd.ok and rd.bias == "SHORT" and abs(rd.confidence - 0.6) < 1e-9
    finally:
        srv.shutdown()
        os.environ.pop("OLLAMA_HOST", None)


def test_control_shadow_now_uses_frame():
    """The /shadow endpoint logic: publish a frame, read via the mock model, log
    it, and fail gracefully when there is no frame."""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            self._send({"models": [{"name": "llama3.2"}]})
        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0") or "0")
            self.rfile.read(n)
            self._send({"response": '{"bias":"LONG","confidence":0.72,"rationale":"trend up"}'})
        def _send(self, obj):
            b = json.dumps(obj).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["OLLAMA_HOST"] = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        from api import terminal_state, control

        class S:
            symbol = "SPY"; spot = 601.30; session = "REGULAR"; source = "SIM"

        class I:
            required = dict(REQ); advisory = {"VWAP": 600.95}; required_passed = True

        terminal_state.publish_frame(snapshot=S(), indicators=I(), signal_status="HOLD")
        st = control.ollama_status()
        assert st["available"] is True and st["model"], st
        r = control.shadow_now()
        assert r["ok"] is True and r["read"]["bias"] == "LONG" and r["det_signal"] == "HOLD", r
        assert control.shadow_ledger(5)["rows"], "shadow_now must append to the ledger"
        terminal_state._LAST_FRAME = {}
        assert control.shadow_now()["ok"] is False, "no-frame path must fail gracefully"
    finally:
        srv.shutdown()
        os.environ.pop("OLLAMA_HOST", None)


def test_execution_never_imports_llm():
    for sub in ("execution", "capital"):
        d = REPO / sub
        if not d.exists():
            continue
        for f in d.glob("*.py"):
            txt = f.read_text(encoding="utf-8")
            assert "llm_ollama" not in txt and "shadow_advisor" not in txt, \
                f"{sub}/{f.name} must not import the LLM advisory layer"


def main() -> None:
    test_parsing_and_clamp()
    test_invalid_bias_becomes_flat()
    test_fail_soft_when_down()
    test_prompt_withholds_deterministic_call()
    test_ledger_round_trip()
    test_http_round_trip_against_mock_ollama()
    test_control_shadow_now_uses_frame()
    test_execution_never_imports_llm()
    print("SHADOW PASS — parse/clamp, fail-soft, prompt independence, ledger, HTTP round-trip, control endpoint, execution isolation")


if __name__ == "__main__":
    main()

#
# api/terminal_server.py
#
# ROGUE:OPS Operator Console — local HTTP server (stdlib only, no deps).
#
#   python -m api.terminal_server      # serves http://localhost:8787
#
# Endpoints:
#   GET  /                 -> the unified console UI (api/console.html)
#   GET  /legacy           -> the original single-panel terminal (api/terminal.html)
#   GET  /state            -> live JSON snapshot (api.terminal_state)
#   GET  /research?symbol=SPY&days=250&cost=2&source=massive_daily[&bar=5+mins]
#                          -> backtest harness result (read-only)
#   POST /control/kill         {"reason": "..."}     -> engage durable cross-process kill
#   POST /control/clear_kill   {}                    -> remove the durable kill file
#   POST /control/arm          {"armed": true|false} -> set the ARM intent flag
#
# Bound to 127.0.0.1 ONLY. This is a personal, single-operator surface; it is
# never exposed off-host. Kill is always available; arm is intent-only and stays
# subordinate to the capital gates.
#

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.terminal_state import get_terminal_state
from api import control

PORT = int(os.getenv("TERMINAL_PORT", "8787"))
HERE = Path(__file__).resolve().parent
CONSOLE_HTML = HERE / "console.html"
LEGACY_HTML = HERE / "terminal.html"
MAX_BODY = 64 * 1024


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # quiet

    def _send(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, status: int = 200):
        self._send(json.dumps(obj, default=str).encode("utf-8"), "application/json", status)

    def _html(self, path: Path):
        try:
            body = path.read_text(encoding="utf-8").encode("utf-8")
        except Exception:
            body = f"<h1>{path.name} not found</h1>".encode("utf-8")
        self._send(body, "text/html; charset=utf-8")

    # ---- GET ----
    def do_GET(self):
        route = urlparse(self.path)
        path = route.path.rstrip("/") or "/"

        if path == "/state":
            self._json(get_terminal_state())
            return
        if path == "/research":
            q = parse_qs(route.query)
            result = control.run_research(
                symbol=(q.get("symbol", ["SPY"])[0] or "SPY").upper(),
                days=_int(q.get("days", ["250"])[0], 250),
                cost_bps=_float(q.get("cost", ["2"])[0], 2.0),
                source=q.get("source", ["massive_daily"])[0],
                bar_size=q.get("bar", ["5 mins"])[0],
            )
            self._json(result)
            return
        if path == "/shadow":
            self._json(control.shadow_now())
            return
        if path == "/shadow/ledger":
            q = parse_qs(route.query)
            self._json(control.shadow_ledger(_int(q.get("limit", ["100"])[0], 100)))
            return
        if path == "/shadow/status":
            self._json(control.ollama_status())
            return
        if path == "/legacy":
            self._html(LEGACY_HTML)
            return
        self._html(CONSOLE_HTML)

    # ---- POST (controls) ----
    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        body = self._read_body()

        if path == "/control/kill":
            self._json(control.engage_kill(body.get("reason") or "operator: console kill"))
            return
        if path == "/control/clear_kill":
            self._json(control.clear_kill())
            return
        if path == "/control/arm":
            self._json(control.set_arm(bool(body.get("armed"))))
            return
        self._json({"ok": False, "error": f"unknown control {path}"}, status=404)

    def _read_body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", "0") or "0")
            if n <= 0 or n > MAX_BODY:
                return {}
            raw = self.rfile.read(n).decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}


def _int(v, default):
    try:
        return int(v)
    except Exception:
        return default


def _float(v, default):
    try:
        return float(v)
    except Exception:
        return default


def main() -> None:
    print(f"ROGUE:OPS Console  ->  http://localhost:{PORT}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), _Handler).serve_forever()


if __name__ == "__main__":
    main()

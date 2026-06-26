#
# api/terminal_server.py
#
# ROGUE:OPS Operator Terminal — local HTTP server (stdlib only, no deps).
#
#   python -m api.terminal_server      # serves http://localhost:8787
#
# Endpoints:
#   GET /            -> the terminal UI (api/terminal.html)
#   GET /state       -> JSON snapshot from api/terminal_state.get_terminal_state()
#
# Runs standalone (shows current singleton state) or alongside the market loop
# (which publishes live frames via terminal_state.publish_frame).
#

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.terminal_state import get_terminal_state

PORT = int(os.getenv("TERMINAL_PORT", "8787"))
HTML_PATH = Path(__file__).resolve().parent / "terminal.html"


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
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] in ("/state", "/state/"):
            body = json.dumps(get_terminal_state(), default=str).encode("utf-8")
            self._send(body, "application/json")
            return
        try:
            body = HTML_PATH.read_text(encoding="utf-8").encode("utf-8")
        except Exception:
            body = b"<h1>terminal.html not found</h1>"
        self._send(body, "text/html; charset=utf-8")


def main() -> None:
    print(f"ROGUE:OPS Terminal  ->  http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), _Handler).serve_forever()


if __name__ == "__main__":
    main()

#
# tools/robinhood_auth.py
#
# One-time OAuth bootstrap for ROGUE:OPS as its OWN Robinhood agent.
#
# ROGUE:OPS connects to the hosted Robinhood Trading MCP server as an MCP
# client and runs the OAuth 2.0 authorization-code flow itself. On first
# connect this also triggers Robinhood's Agentic-account onboarding. The flow
# opens your browser for the desktop consent, then persists the access token so
# the headless OMS can reuse it (broker/robinhood_mcp.py reads it).
#
# Run from repo root (desktop, browser available):
#   pip install -r requirements-robinhood.txt
#   python tools\robinhood_auth.py                 # full OAuth browser flow
#   python tools\robinhood_auth.py --paste         # fallback: paste a token you already have
#   python tools\robinhood_auth.py --show          # print token-file location + status
#
# Outputs:
#   - <token_file>            plain access token  (ROBINHOOD_MCP_TOKEN_FILE, or
#                             %LOCALAPPDATA%\rogueops\rh_token.txt by default)
#   - <token_file>.json       full token cache (access/refresh/expiry) for refresh
#
# CAVEAT: the OAuth flow is built to the MCP spec (dynamic client registration +
# PKCE + localhost redirect) but is unverified against Robinhood's live handshake
# from this environment. If it fails, use --paste with a token obtained by
# connecting any MCP client (e.g. Claude Desktop custom connector) to the same
# URL, then report the error and we'll adjust.
#

import argparse
import asyncio
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.robinhood_mcp import _mcp_url  # noqa: E402

try:
    from governance.paths import ops_home, ensure_dir
except Exception:  # pragma: no cover - fallback if run oddly
    def ops_home() -> Path:
        base = os.getenv("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "rogueops" if os.name == "nt" else Path("/opt/rogueops")

    def ensure_dir(p: Path) -> Path:
        p.mkdir(parents=True, exist_ok=True)
        return p


OAUTH_PORT = int(os.getenv("ROBINHOOD_OAUTH_PORT", "33420"))
REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/callback"


def token_file() -> Path:
    override = os.getenv("ROBINHOOD_MCP_TOKEN_FILE")
    if override:
        return Path(override)
    return ensure_dir(ops_home()) / "rh_token.txt"


def _write_token(access_token: str, full: dict | None = None) -> Path:
    tf = token_file()
    ensure_dir(tf.parent)
    tf.write_text(access_token.strip(), encoding="utf-8")
    if full is not None:
        tf.with_suffix(tf.suffix + ".json").write_text(
            json.dumps(full, indent=2), encoding="utf-8"
        )
    return tf


# ======================================================================
# Local one-shot callback server (captures ?code=...&state=...)
# ======================================================================

class _CallbackServer:
    def __init__(self, port: int):
        self._port = port
        self._code: str | None = None
        self._state: str | None = None
        self._event = threading.Event()
        self._httpd: HTTPServer | None = None

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):  # silence
                pass

            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                outer._code = (qs.get("code") or [None])[0]
                outer._state = (qs.get("state") or [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h3>ROGUE:OPS authorized. You can close this tab.</h3></body></html>"
                )
                outer._event.set()

        self._httpd = HTTPServer(("localhost", self._port), Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def wait(self, timeout: float = 300.0) -> tuple[str, str]:
        if not self._event.wait(timeout):
            raise TimeoutError("OAuth callback not received within timeout")
        if not self._code:
            raise RuntimeError("OAuth callback missing authorization code")
        return self._code, self._state or ""

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()


# ======================================================================
# OAuth flow (MCP SDK)
# ======================================================================

async def _run_oauth() -> None:
    # Lazy imports so the module loads without the SDK installed.
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.client.auth import OAuthClientProvider, TokenStorage
    from mcp.shared.auth import OAuthClientMetadata, OAuthClientInformationFull, OAuthToken

    url = _mcp_url()
    cb = _CallbackServer(OAUTH_PORT)
    cb.start()

    class _MemStorage(TokenStorage):
        def __init__(self):
            self._tokens: "OAuthToken | None" = None
            self._client: "OAuthClientInformationFull | None" = None

        async def get_tokens(self):
            return self._tokens

        async def set_tokens(self, tokens):
            self._tokens = tokens

        async def get_client_info(self):
            return self._client

        async def set_client_info(self, client_info):
            self._client = client_info

    storage = _MemStorage()

    async def redirect_handler(authorization_url: str) -> None:
        print(f"\nOpening browser for Robinhood authorization:\n  {authorization_url}\n")
        print("If the browser does not open, paste that URL into a desktop browser.")
        webbrowser.open(authorization_url)

    async def callback_handler() -> tuple[str, str]:
        print(f"Waiting for the OAuth redirect on {REDIRECT_URI} ...")
        return cb.wait()

    oauth = OAuthClientProvider(
        server_url=url,
        client_metadata=OAuthClientMetadata(
            client_name="ROGUE-OPS",
            redirect_uris=[REDIRECT_URI],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        ),
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    try:
        async with streamablehttp_client(url, auth=oauth) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print(f"\nAuthorized. Server exposes {len(tools.tools)} tool(s).")
    finally:
        cb.stop()

    tokens = await storage.get_tokens()
    if tokens is None or not getattr(tokens, "access_token", None):
        raise RuntimeError("OAuth completed but no access token was stored")

    full = tokens.model_dump() if hasattr(tokens, "model_dump") else dict(tokens)
    tf = _write_token(tokens.access_token, full)
    print(f"\nToken saved -> {tf}")
    print("Set this for the OMS:")
    print(f'  $env:ROBINHOOD_MCP_TOKEN_FILE = "{tf}"')
    print("Then run:  python tools\\robinhood_mcp_probe.py")


# ======================================================================
# Paste fallback + status
# ======================================================================

def _paste_token() -> None:
    print("Paste the Robinhood agentic-account access token, then press Enter:")
    tok = input("> ").strip()
    if not tok:
        raise SystemExit("No token entered.")
    tf = _write_token(tok)
    print(f"\nToken saved -> {tf}")
    print(f'Set:  $env:ROBINHOOD_MCP_TOKEN_FILE = "{tf}"')
    print("Validate:  python tools\\robinhood_mcp_probe.py")


def _show() -> None:
    tf = token_file()
    print(f"MCP URL    : {_mcp_url()}")
    print(f"Token file : {tf}")
    print(f"Exists     : {tf.exists()}")
    print(f"Redirect   : {REDIRECT_URI}")


def main() -> None:
    ap = argparse.ArgumentParser(description="ROGUE:OPS Robinhood OAuth bootstrap")
    ap.add_argument("--paste", action="store_true", help="paste an existing access token instead of running OAuth")
    ap.add_argument("--show", action="store_true", help="print token-file location and status")
    args = ap.parse_args()

    if args.show:
        _show()
        return
    if args.paste:
        _paste_token()
        return

    try:
        asyncio.run(_run_oauth())
    except ImportError as e:
        raise SystemExit(
            "mcp SDK not installed. `pip install -r requirements-robinhood.txt`, "
            f"or use --paste. ({e})"
        )
    except Exception as e:
        print(f"\nOAuth flow failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("Fallback: obtain a token by connecting any MCP client to "
              f"{_mcp_url()} (e.g. Claude Desktop custom connector), then run "
              "`python tools\\robinhood_auth.py --paste`.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

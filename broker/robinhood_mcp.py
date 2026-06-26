#
# broker/robinhood_mcp.py
#
# Robinhood Agentic Trading — MCP client transport.
#
# Robinhood exposes a HOSTED, REMOTE MCP server (HTTP transport):
#     https://agent.robinhood.com/mcp/trading
# scoped to a sandboxed "Agentic" sub-account, authenticated via OAuth 2.0.
#
# This module is a thin, headless MCP CLIENT around that endpoint. The OAuth
# access token is obtained ONCE interactively on a desktop (open the agentic
# account in the Robinhood app and authorize the agent) and then supplied to
# this process via config (env var or token file). Subsequent calls are headless.
#
# The `mcp` Python SDK and asyncio are imported lazily inside methods, so this
# module (and the broker boundary) import cleanly without the SDK installed —
# preserving SIM-safe imports.
#
# IMPORTANT — wire schema is not assumed:
#   The exact order-tool NAME, its argument keys, and the result shape must be
#   confirmed against the live server. Run `tools/robinhood_mcp_probe.py` once
#   you have a token to dump the real tool list, then lock the mapping below.
#   The defaults here are best-effort and centralized for easy correction.
#

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MCP_URL = "https://agent.robinhood.com/mcp/trading"

# Candidate names for the place-order tool (confirm via probe; override with
# ROBINHOOD_ORDER_TOOL). Matching is case-insensitive and exact-first.
_ORDER_TOOL_CANDIDATES = ("place_order", "submit_order", "create_order", "place_equity_order")

# Keys we look for when extracting a broker order id from a tool result.
_ORDER_ID_KEYS = ("order_id", "orderId", "id", "order_number")


class RobinhoodAuthError(RuntimeError):
    """Raised when no usable OAuth token is available (re-authorization needed)."""


class RobinhoodMCPError(RuntimeError):
    """Raised on MCP transport/tool errors."""


def _load_token() -> str:
    """
    Resolve the OAuth access token for the agentic account.

    Order: ROBINHOOD_MCP_TOKEN env -> ROBINHOOD_MCP_TOKEN_FILE contents.
    Minting/refreshing the token is a one-time interactive desktop step
    (see ROBINHOOD_SETUP.md); this process only consumes it.
    """
    tok = os.getenv("ROBINHOOD_MCP_TOKEN")
    if tok:
        return tok.strip()

    path = os.getenv("ROBINHOOD_MCP_TOKEN_FILE")
    if path and os.path.isfile(path):
        return Path(path).read_text(encoding="utf-8").strip()

    raise RobinhoodAuthError(
        "No Robinhood token. Set ROBINHOOD_MCP_TOKEN or ROBINHOOD_MCP_TOKEN_FILE "
        "after completing the one-time desktop OAuth authorization (see ROBINHOOD_SETUP.md)."
    )


def _mcp_url() -> str:
    return os.getenv("ROBINHOOD_MCP_URL", DEFAULT_MCP_URL)


class RobinhoodMCPClient:
    """
    Minimal synchronous facade over the async MCP SDK. Each call opens a
    short-lived session (simple + robust); can be upgraded to a persistent
    session later if call volume warrants it.
    """

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        self.url = url or _mcp_url()
        self._token = token  # resolved lazily so import/instantiation never fails

    # -- internals ---------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        token = self._token or _load_token()
        return {"Authorization": f"Bearer {token}"}

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    async def _with_session(self, fn):
        # Lazy SDK import keeps the module SIM-safe / installable on demand.
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as e:  # pragma: no cover
            raise RobinhoodMCPError(
                "mcp SDK not installed. `pip install -r requirements-robinhood.txt`"
            ) from e

        async with streamablehttp_client(self.url, headers=self._headers()) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)

    # -- public API --------------------------------------------------------

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return the live tool list (name + input schema). Use for probing."""
        async def _fn(session):
            resp = await session.list_tools()
            return [
                {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
                for t in resp.tools
            ]
        return self._run(self._with_session(_fn))

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool and return a normalized {structured, text, raw} result."""
        async def _fn(session):
            res = await session.call_tool(name, arguments=arguments)
            return _normalize_tool_result(res)
        return self._run(self._with_session(_fn))

    def resolve_order_tool(self) -> str:
        """Pick the place-order tool: explicit override, else candidate match."""
        forced = os.getenv("ROBINHOOD_ORDER_TOOL")
        if forced:
            return forced
        names = {t["name"].lower(): t["name"] for t in self.list_tools()}
        for cand in _ORDER_TOOL_CANDIDATES:
            if cand in names:
                return names[cand]
        raise RobinhoodMCPError(
            f"Could not find an order tool among {sorted(names.values())}. "
            f"Set ROBINHOOD_ORDER_TOOL to the correct name (run the probe to inspect)."
        )


def _normalize_tool_result(res) -> Dict[str, Any]:
    """Coerce an MCP CallToolResult into a plain dict (structured preferred)."""
    structured = getattr(res, "structuredContent", None)
    text = None
    content = getattr(res, "content", None) or []
    for block in content:
        if getattr(block, "type", None) == "text" or hasattr(block, "text"):
            text = getattr(block, "text", None)
            break
    return {
        "is_error": bool(getattr(res, "isError", False)),
        "structured": structured,
        "text": text,
    }


def map_intent_to_order_args(intent, quantity: int) -> Dict[str, Any]:
    """
    Map a canonical ExecutionIntent -> order-tool arguments (EQUITIES).

    NOTE: argument keys are best-effort and MUST be confirmed against the live
    tool's input schema (run the probe). Centralized here for one-line fixes.
    No price field exists on ExecutionIntent yet, so order type is 'market'.
    """
    return {
        "symbol": intent.symbol,
        "side": "buy" if intent.action == "BUY" else "sell",
        "quantity": quantity,
        "type": "market",
        "time_in_force": "day",
    }


def extract_order_id(result: Dict[str, Any]) -> Optional[str]:
    """Pull a broker order id out of a normalized tool result, if present."""
    src = result.get("structured")
    if isinstance(src, dict):
        for k in _ORDER_ID_KEYS:
            if k in src and src[k] is not None:
                return str(src[k])
        # sometimes nested under "order"
        order = src.get("order")
        if isinstance(order, dict):
            for k in _ORDER_ID_KEYS:
                if order.get(k) is not None:
                    return str(order[k])
    return None

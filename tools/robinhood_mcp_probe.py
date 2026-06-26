#
# tools/robinhood_mcp_probe.py
#
# One-off probe for the Robinhood Agentic Trading MCP server.
#
# Run this AFTER completing the one-time desktop OAuth authorization and setting
# a token (see ROBINHOOD_SETUP.md). It connects to the live MCP endpoint and
# dumps the real tool list + input schemas, so the order-tool name and argument
# mapping in broker/robinhood_mcp.py can be confirmed against ground truth.
#
# Run from repo root:
#   python tools\robinhood_mcp_probe.py        (Windows)
#   python tools/robinhood_mcp_probe.py        (macOS/Linux)
#
# Requires: pip install -r requirements-robinhood.txt
#           ROBINHOOD_MCP_TOKEN (or ROBINHOOD_MCP_TOKEN_FILE) set.
#

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.robinhood_mcp import RobinhoodMCPClient, _mcp_url


def main() -> None:
    print(f"Connecting to Robinhood MCP: {_mcp_url()}")
    client = RobinhoodMCPClient()
    tools = client.list_tools()

    print(f"\nDiscovered {len(tools)} tool(s):\n")
    for t in tools:
        print(f"- {t['name']}")
        if t.get("description"):
            print(f"    {t['description']}")
        schema = t.get("input_schema")
        if schema:
            props = (schema or {}).get("properties", {})
            if props:
                print(f"    args: {', '.join(sorted(props.keys()))}")
            print("    schema: " + json.dumps(schema)[:400])
        print()

    order_like = [t["name"] for t in tools if "order" in t["name"].lower()]
    if order_like:
        print(f"Likely order tool(s): {order_like}")
        print("If the name differs from broker/robinhood_mcp.py defaults, set "
              "ROBINHOOD_ORDER_TOOL and confirm the arg keys in map_intent_to_order_args().")


if __name__ == "__main__":
    main()

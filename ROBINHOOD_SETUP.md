# ROGUE:OPS — Robinhood Agentic Broker Setup

Robinhood is wired as the **equities** broker behind the multi-broker boundary.
It trades through Robinhood's hosted **Agentic Trading MCP server**, scoped to a
**sandboxed agentic sub-account** (isolated from your main portfolio).

> **Status:** Robinhood Agentic Trading is **equities-only** today. Options route
> to IBKR automatically; pointing an option order at Robinhood is blocked
> fail-closed by the boundary. When Robinhood enables options, add `"OPT"` to
> `_SUPPORTED_SEC_TYPES` in `broker/robinhood_broker.py`.

## One-time setup (you must do this — it requires a desktop + your account)

1. **Open a Robinhood Agentic account** and authorize an agent. This is a
   desktop-only OAuth consent: Robinhood opens a consent screen, you approve the
   agent, and access is bounded to the segregated agentic sub-account.
   Endpoint: `https://agent.robinhood.com/mcp/trading`.

2. **Obtain an OAuth access token** for that agentic account from the
   authorization flow, and make it available to ROGUE:OPS:

   ```powershell
   # Option A: environment variable
   $env:ROBINHOOD_MCP_TOKEN = "<access-token>"

   # Option B: token file (path in env)
   $env:ROBINHOOD_MCP_TOKEN_FILE = "$env:LOCALAPPDATA\rogueops\rh_token.txt"
   ```

3. **Install the MCP client dependency:**

   ```powershell
   python -m pip install -r requirements-robinhood.txt
   ```

4. **Probe the live server** to confirm the real tool list + argument schema:

   ```powershell
   python tools\robinhood_mcp_probe.py
   ```

   If the order tool name isn't one of the built-in candidates, set
   `ROBINHOOD_ORDER_TOOL` and confirm the argument keys in
   `map_intent_to_order_args()` (`broker/robinhood_mcp.py`).

## Routing

Selection happens in `broker/broker_runtime.py`:

- Options → **IBKR** (only options-capable broker today)
- Equities → **Robinhood** (default; override with `EQUITY_BROKER`)
- Force a specific broker with `BROKER=IBKR|ROBINHOOD`

The boundary is **fail-closed**: any instrument a broker can't trade is rejected
(`BROKER_UNSUPPORTED`) rather than mis-routed.

## Known follow-ups

- **Token refresh.** This process consumes a pre-minted token; headless refresh
  (refresh-token flow) is a `TODO` hook in `broker/robinhood_mcp.py`.
- **Order type.** `ExecutionIntent` has no price field yet, so equity orders are
  submitted `market`. Add marketable-limit support when price plumbing exists.
- **Wire schema.** Tool name/args/result shape are best-effort defaults until
  confirmed by the probe against the live server.

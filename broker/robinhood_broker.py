#
# broker/robinhood_broker.py
#
# Robinhood implementation of the BrokerRuntime Protocol.
#
# Robinhood Agentic Trading (MCP) is EQUITIES-ONLY in beta (launched 2026-05-27);
# options, crypto, futures, and event contracts are roadmapped with no published
# date. supports() reflects that, so the boundary fails CLOSED if an option
# intent is ever routed here. Flip "OPT" into _SUPPORTED_SEC_TYPES when Robinhood
# enables options.
#
# Order placement goes through the hosted Robinhood MCP server via the headless
# client in broker/robinhood_mcp.py. The OAuth token is provisioned out of band
# (one-time desktop authorization — see ROBINHOOD_SETUP.md).
#

from typing import Optional

from execution.execution_contracts import ExecutionIntent
from broker.broker_runtime import BrokerOrderResult


class RobinhoodBroker:
    name = "ROBINHOOD"

    # Equities only (Agentic Trading beta). Add "OPT" when Robinhood enables it.
    _SUPPORTED_SEC_TYPES = {"STK"}

    def __init__(self):
        self._client = None  # lazily constructed; avoids importing mcp at import time

    def supports(self, intent: ExecutionIntent) -> bool:
        return intent.sec_type in self._SUPPORTED_SEC_TYPES

    def _get_client(self):
        if self._client is None:
            from broker.robinhood_mcp import RobinhoodMCPClient
            self._client = RobinhoodMCPClient()
        return self._client

    def execute_intent(
        self,
        intent: ExecutionIntent,
        override_quantity: Optional[int] = None,
    ) -> BrokerOrderResult:
        # Defensive: capability is also enforced at the boundary (fail-closed),
        # but never let a non-equity intent reach the order tool.
        if intent.sec_type not in self._SUPPORTED_SEC_TYPES:
            raise ValueError(
                f"Robinhood cannot trade sec_type={intent.sec_type} (equities only)"
            )

        from broker.robinhood_mcp import (
            map_intent_to_order_args,
            extract_order_id,
            RobinhoodMCPError,
        )

        qty = override_quantity if override_quantity is not None else intent.quantity
        client = self._get_client()

        tool = client.resolve_order_tool()
        args = map_intent_to_order_args(intent, qty)
        result = client.call_tool(tool, args)

        if result.get("is_error"):
            raise RobinhoodMCPError(f"Robinhood order tool error: {result.get('text')}")

        order_id = extract_order_id(result)

        return BrokerOrderResult(
            # order_id is an int in the Protocol; RH ids may be non-numeric, so
            # we hash to a stable int and keep the canonical id in raw.
            order_id=_as_int_order_id(order_id),
            raw={
                "broker": "ROBINHOOD",
                "symbol": intent.symbol,
                "side": args["side"],
                "quantity": qty,
                "tool": tool,
                "order_id": order_id,
                "result": result,
            },
        )


def _as_int_order_id(order_id) -> int:
    if order_id is None:
        return 0
    try:
        return int(order_id)
    except (TypeError, ValueError):
        import hashlib
        return int(hashlib.sha256(str(order_id).encode()).hexdigest()[:8], 16)


_RH_BROKER: Optional["RobinhoodBroker"] = None


def get_robinhood_broker() -> "RobinhoodBroker":
    global _RH_BROKER
    if _RH_BROKER is None:
        _RH_BROKER = RobinhoodBroker()
    return _RH_BROKER

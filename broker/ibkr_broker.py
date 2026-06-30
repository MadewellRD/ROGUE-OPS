#
# broker/ibkr_broker.py
#
# IBKR implementation of the BrokerRuntime Protocol.
#
# IBKR is the OPTIONS-capable broker (and also supports equities). It places
# orders over the single long-lived IBKR session owned by IBKRRuntime.
#
# Submission-only semantics (TWS-compliant): execute_intent constructs the
# contract + order, submits it, and returns the broker order id. Fill tracking
# is handled out of band by the runtime/audit layers.
#
# ibapi is imported lazily inside execute_intent so this module imports cleanly
# in SIM and on machines without the IBKR SDK installed.
#

import os
from typing import Optional

from execution.execution_contracts import ExecutionIntent
from broker.broker_runtime import BrokerOrderResult

# IBKR supports both equities and options.
_SUPPORTED_SEC_TYPES = {"STK", "OPT"}

# Equities use MKT (penny-wide, liquid). Options use a MARKETABLE LIMIT priced
# off the live NBBO — 0DTE spreads are wide/gappy, so a naked MKT is unsafe.
#   ROGUE_FORCE_MKT=1        force MKT (escape hatch when no market-data sub)
#   ROGUE_LIMIT_BUFFER_PCT   widen the marketable limit for fill probability


class IBKRBroker:
    name = "IBKR"

    def __init__(self, account_id: Optional[str] = None):
        self.account_id = account_id or os.getenv("IBKR_ACCOUNT_ID")

    def supports(self, intent: ExecutionIntent) -> bool:
        return intent.sec_type in _SUPPORTED_SEC_TYPES

    def execute_intent(
        self,
        intent: ExecutionIntent,
        override_quantity: Optional[int] = None,
    ) -> BrokerOrderResult:
        from ibapi.order import Order

        from broker.ibkr_runtime import get_ibkr_runtime
        from broker.ibkr_contracts import (
            build_stock_contract,
            build_option_contract,
        )

        runtime = get_ibkr_runtime()
        qty = override_quantity if override_quantity is not None else intent.quantity

        if intent.sec_type == "OPT":
            if intent.option is None:
                raise ValueError("OPT intent missing OptionSpec")
            contract = build_option_contract(intent.symbol, intent.option)
        else:
            contract = build_stock_contract(intent.symbol)

        order = Order()
        order.action = intent.action            # BUY / SELL (authoritative)
        order.totalQuantity = qty
        order.tif = "DAY"
        # ibapi 9.81 defaults these deprecated attributes to True; TWS 10.x
        # rejects orders that carry them (error 10268/10269). Clear them.
        order.eTradeOnly = False
        order.firmQuoteOnly = False
        if self.account_id:
            order.account = self.account_id

        # --- Order type / pricing ---
        force_mkt = os.getenv("ROGUE_FORCE_MKT", "").lower() in ("1", "true", "yes")
        buffer_pct = float(os.getenv("ROGUE_LIMIT_BUFFER_PCT", "0") or 0)
        limit_px = None

        if intent.sec_type == "OPT" and not force_mkt:
            from broker.pricing import marketable_limit, UnpriceableError
            bid, ask = runtime.get_quote(contract)
            try:
                limit_px = marketable_limit(
                    intent.action, bid, ask, buffer_pct=buffer_pct
                )
            except UnpriceableError as e:
                raise RuntimeError(
                    f"No quote to price {intent.symbol} option (bid={bid}, ask={ask}); "
                    f"refusing naked market order. Set ROGUE_FORCE_MKT=1 to override. ({e})"
                )
            order.orderType = "LMT"
            order.lmtPrice = limit_px
        else:
            order.orderType = "MKT"

        oid = runtime.next_order_id()
        runtime.placeOrder(oid, contract, order)

        # Capture the real fill so downstream P&L / daily-loss governance is
        # exact (not entry-only). None if it doesn't fill within the window —
        # the position bridge then declines to record an unconfirmed fill.
        fill_timeout = float(os.getenv("ROGUE_FILL_TIMEOUT_SECONDS", "6"))
        fill_price = runtime.wait_for_fill(oid, timeout=fill_timeout)

        # ROGUE-003: never leave a working order behind. If it did not fill in
        # the window, cancel it, then re-check briefly in case it filled during
        # the cancel race. This stops a timed-out order from lingering at the
        # broker and lets an EXIT safely retry without double-submitting.
        if fill_price is None:
            try:
                runtime.cancel_order(oid)
            except Exception as e:
                print(f"[IBKR][CANCEL_ERROR] oid={oid}: {e}")
            fill_price = runtime.wait_for_fill(oid, timeout=2.0)

        return BrokerOrderResult(
            order_id=oid,
            raw={
                "broker": "IBKR",
                "symbol": intent.symbol,
                "sec_type": intent.sec_type,
                "action": intent.action,
                "quantity": qty,
                "order_type": order.orderType,
                "limit_price": limit_px,
                "fill_price": fill_price,
                "status": runtime.order_status(oid),
            },
        )


_IBKR_BROKER: Optional["IBKRBroker"] = None


def get_ibkr_broker() -> "IBKRBroker":
    global _IBKR_BROKER
    if _IBKR_BROKER is None:
        _IBKR_BROKER = IBKRBroker()
    return _IBKR_BROKER

#
# ibkr_client.py
#
# IBKR execution client using IBAPI (TWS / IB Gateway).
# This file intentionally does NOT use Client Portal Gateway.
#
# Assumptions:
# - IBKR TWS or IB Gateway is running locally
# - Paper trading port = 7497
# - Live trading port = 7496
#
# ROGUE Lite rules:
# - No startup-time IBKR dependency
# - Connect only at execution time
# - Deterministic failure semantics
#

import threading
import time
from typing import Dict, Any

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order


# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------

IBKR_HOST = "127.0.0.1"
IBKR_PAPER_PORT = 7497
IBKR_LIVE_PORT = 7496

# Use paper by default
IBKR_PORT = IBKR_PAPER_PORT

CLIENT_ID_BASE = 7000


# -------------------------------------------------
# IBAPI CLIENT
# -------------------------------------------------

class _IBKRClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None
        self.connected_event = threading.Event()
        self.order_status_event = threading.Event()
        self.last_order_status = None

    # ----- Connection -----

    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self.connected_event.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        # IBKR uses error() for status messages as well.
        print(f"[IBKR][ERROR] code={errorCode} msg={errorString}")

    def orderStatus(
        self,
        orderId,
        status,
        filled,
        remaining,
        avgFillPrice,
        permId,
        parentId,
        lastFillPrice,
        clientId,
        whyHeld,
        mktCapPrice,
    ):
        self.last_order_status = status
        self.order_status_event.set()


# -------------------------------------------------
# PUBLIC EXECUTION FUNCTION
# -------------------------------------------------

def place_order(account_id: str, order_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Places an order via IBAPI.

    Returns a normalized execution result dict.
    Never raises.
    """

    client = _IBKRClient()

    try:
        client_id = CLIENT_ID_BASE + int(time.time()) % 1000
        client.connect(IBKR_HOST, IBKR_PORT, client_id)

        api_thread = threading.Thread(target=client.run, daemon=True)
        api_thread.start()

        if not client.connected_event.wait(timeout=5):
            return {
                "status": "ERROR",
                "reason": "IBKR_CONNECT_TIMEOUT",
            }

        # -----------------------------
        # Build contract
        # -----------------------------
        contract = Contract()
        contract.conId = order_details["conid"]
        contract.exchange = "SMART"
        contract.secType = "STK"
        contract.currency = "USD"

        # -----------------------------
        # Build order
        # -----------------------------
        order = Order()
        order.action = order_details["side"]
        order.orderType = order_details["orderType"]
        order.totalQuantity = order_details["quantity"]
        order.tif = order_details.get("tif", "DAY")

        if "price" in order_details:
            order.lmtPrice = order_details["price"]

        order_id = client.next_order_id
        client.placeOrder(order_id, contract, order)

        # Wait briefly for broker acknowledgement
        client.order_status_event.wait(timeout=5)

        return {
            "status": "SUBMITTED",
            "broker_order_id": str(order_id),
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "reason": str(e),
        }

    finally:
        try:
            client.disconnect()
        except Exception:
            pass

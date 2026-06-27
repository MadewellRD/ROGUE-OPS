#
# broker/ibkr_runtime.py
#
# IBKR Runtime — Broker Access Plane (SEALED)
# Brokerage-Grade OMS Infrastructure
#
# This module is the SINGLE authoritative interface to IBKR.
#
# Responsibilities:
# - Own exactly one IBKR API session
# - Maintain continuous broker connectivity
# - Stream account state (accountSummary)
# - Maintain live in-memory broker truth
# - Periodically snapshot capital into balance_store
# - Provide execution transport via the same session
#
# Explicitly NOT responsible for:
# - Trading decisions
# - Capital authorization
# - Risk logic
# - Strategy or signals
#

import time
import threading
import datetime as dt
from typing import Dict, Optional

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from governance.kill_switch import kill_active
from capital.balance_store import write_snapshot
from capital.account_balance_authority import AccountBalanceSnapshot


# ==================================================
# Singleton Runtime Handle
# ==================================================

_RUNTIME = None
_RUNTIME_LOCK = threading.Lock()


# ==================================================
# IBKR Runtime
# ==================================================

class IBKRRuntime(EWrapper, EClient):
    """
    Long-lived, streaming IBKR runtime.

    This class MUST be instantiated exactly once per process.
    """

    SNAPSHOT_INTERVAL_SECONDS = 2

    def __init__(self, host: str = "127.0.0.1", port: int = 7497):
        EClient.__init__(self, self)

        # ------------------------
        # Connection / Health
        # ------------------------
        self._ready = threading.Event()
        self._connected = False

        # ------------------------
        # Order id sequencing (monotonic, thread-safe)
        # ------------------------
        self._next_order_id: Optional[int] = None
        self._order_id_lock = threading.Lock()

        # Last known status / broker message / fill per order id
        self._order_status: Dict[int, str] = {}
        self._order_messages: Dict[int, str] = {}
        self._order_fills: Dict[int, dict] = {}

        # Market-data snapshot plumbing (for marketable-limit pricing)
        self._md_req_id = 90000
        self._quotes: Dict[int, Dict[str, float]] = {}
        self._quote_events: Dict[int, threading.Event] = {}

        # ------------------------
        # Account State (STREAMING)
        # ------------------------
        self._acct_summary: Dict[str, str] = {}
        self._acct_currency: Optional[str] = None
        self._last_update_utc: Optional[str] = None

        # ------------------------
        # Snapshot Thread
        # ------------------------
        self._snapshot_thread = threading.Thread(
            target=self._snapshot_loop,
            daemon=True,
        )

        # ------------------------
        # Connect Once, Stay Connected
        # ------------------------
        self.connect(
            host,
            port,
            clientId=int(time.time()) % 10_000,
        )

        threading.Thread(target=self.run, daemon=True).start()

        if not self._ready.wait(timeout=15):
            raise RuntimeError("IBKR_RUNTIME_INIT_TIMEOUT")

        # ------------------------
        # Subscribe to Account Summary (STREAMING)
        # ------------------------
        self.reqAccountSummary(
            reqId=1,
            groupName="All",
            tags="NetLiquidation,AvailableFunds,ExcessLiquidity,BuyingPower",
        )

        self._snapshot_thread.start()

    # ==================================================
    # Lifecycle Callbacks
    # ==================================================

    def nextValidId(self, orderId: int):
        """
        Signals that the session is live and usable, and seeds the
        monotonic order-id sequence used for order placement.
        """
        with self._order_id_lock:
            self._next_order_id = orderId
        self._connected = True
        self._ready.set()

    def next_order_id(self) -> int:
        """
        Return the next valid order id and advance the sequence.
        Thread-safe. Raises if the session has not yet been seeded.
        """
        with self._order_id_lock:
            if self._next_order_id is None:
                raise RuntimeError("IBKR_ORDER_ID_UNAVAILABLE")
            oid = self._next_order_id
            self._next_order_id += 1
            return oid

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
        """Record broker acknowledgement + fill status/price per order id."""
        with self._order_id_lock:
            self._order_status[orderId] = status
            self._order_fills[orderId] = {
                "filled": filled,
                "avg_fill_price": avgFillPrice,
                "status": status,
            }

    def order_status(self, order_id: int) -> Optional[str]:
        """Return the last known status for an order id (None if unseen)."""
        with self._order_id_lock:
            return self._order_status.get(order_id)

    def order_message(self, order_id: int) -> Optional[str]:
        """Return the last broker message (warning/reject) for an order id."""
        with self._order_id_lock:
            return self._order_messages.get(order_id)

    def fill_price(self, order_id: int) -> Optional[float]:
        """Return the average fill price for an order, or None if not yet filled."""
        with self._order_id_lock:
            f = self._order_fills.get(order_id)
        if f and f.get("filled") and f.get("avg_fill_price"):
            try:
                return float(f["avg_fill_price"])
            except (TypeError, ValueError):
                return None
        return None

    def wait_for_fill(self, order_id: int, timeout: float = 6.0) -> Optional[float]:
        """
        Block up to `timeout` seconds for an order to fill; return the average
        fill price, or None if it did not fill in time (caller decides policy).
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            fp = self.fill_price(order_id)
            if fp is not None and fp > 0:
                return fp
            time.sleep(0.1)
        return self.fill_price(order_id)

    # ==================================================
    # Market-data snapshot (for marketable-limit pricing)
    # ==================================================

    def _next_md_req_id(self) -> int:
        with self._order_id_lock:
            self._md_req_id += 1
            return self._md_req_id

    def get_quote(self, contract, timeout: float = 3.0):
        """
        One-shot NBBO snapshot for a contract. Returns (bid, ask); either may be
        None if unavailable (e.g. no market-data subscription). Never raises.
        Handles delayed ticks (66/67) so paper accounts without OPRA still price.
        """
        req_id = self._next_md_req_id()
        ev = threading.Event()
        with self._order_id_lock:
            self._quotes[req_id] = {}
            self._quote_events[req_id] = ev
        try:
            self.reqMktData(req_id, contract, "", True, False, [])
        except Exception as e:
            print(f"[IBKR][QUOTE_ERROR] {e}")
        ev.wait(timeout)
        with self._order_id_lock:
            q = self._quotes.pop(req_id, {})
            self._quote_events.pop(req_id, None)
        try:
            self.cancelMktData(req_id)
        except Exception:
            pass
        return q.get("bid"), q.get("ask")

    def tickPrice(self, reqId, tickType, price, attrib):
        # 1/66 = bid, 2/67 = ask, 4/68 = last (66-68 are delayed equivalents)
        with self._order_id_lock:
            q = self._quotes.get(reqId)
            if q is None:
                return
            if tickType in (1, 66):
                q["bid"] = price
            elif tickType in (2, 67):
                q["ask"] = price
            elif tickType in (4, 68):
                q["last"] = price
            have_both = "bid" in q and "ask" in q
            ev = self._quote_events.get(reqId)
        if have_both and ev:
            ev.set()

    def tickSnapshotEnd(self, reqId):
        with self._order_id_lock:
            ev = self._quote_events.get(reqId)
        if ev:
            ev.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=None):
        """
        IBKR error and status channel.
        """
        level = "INFO" if errorCode in (2104, 2106, 2158) else "ERROR"
        print(f"[IBKR][{level}] code={errorCode} msg={errorString}")

        # Associate order/request-scoped messages (reqId == orderId for orders).
        if reqId is not None and reqId > 0:
            with self._order_id_lock:
                self._order_messages[reqId] = f"{errorCode}: {errorString}"

        # Treat hard disconnects as unhealthy
        if errorCode in (-1, 507, 1100):
            self._connected = False

    # ==================================================
    # Account Summary (STREAMING CALLBACKS)
    # ==================================================

    def accountSummary(self, reqId, account, tag, value, currency):
        """
        Streaming account state updates.
        """
        self._acct_summary[tag] = value

        if currency:
            self._acct_currency = currency

        self._last_update_utc = (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def accountSummaryEnd(self, reqId):
        """
        Informational only. Stream remains active.
        """
        pass

    # ==================================================
    # Capital Snapshot Loop (AUTHORITATIVE FEED)
    # ==================================================

    def _snapshot_loop(self):
        """
        Periodically derives deterministic capital snapshots
        from the live streaming broker state.
        """

        while True:
            time.sleep(self.SNAPSHOT_INTERVAL_SECONDS)

            # Kill switch dominance
            if kill_active():
                continue

            # Broker connectivity required
            if not self._connected:
                continue

            # Require at least one valid update
            if not self._acct_currency:
                continue

            try:
                snapshot = AccountBalanceSnapshot(
                    account_id="IBKR",
                    currency=self._acct_currency,
                    net_liquidation=float(self._acct_summary["NetLiquidation"]),
                    available_funds=float(self._acct_summary["AvailableFunds"]),
                    excess_liquidity=float(self._acct_summary["ExcessLiquidity"]),
                    buying_power=float(self._acct_summary["BuyingPower"]),
                    timestamp_utc=self._last_update_utc,
                    source="CAPITAL",
                    snapshot_hash=None,  # computed downstream
                )

                write_snapshot(snapshot)

            except Exception as e:
                # Fail closed by staleness; do not crash runtime
                print(f"[IBKR][SNAPSHOT_ERROR] {e}")


# ==================================================
# Singleton Accessor
# ==================================================

def get_ibkr_runtime() -> IBKRRuntime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            # Honor IBKR_HOST/IBKR_PORT so execution follows the data feed to
            # Gateway (paper 4002) and, in a container, to host.docker.internal.
            import os
            _RUNTIME = IBKRRuntime(
                host=os.getenv("IBKR_HOST", "127.0.0.1"),
                port=int(os.getenv("IBKR_PORT", "7497")),
            )
        return _RUNTIME

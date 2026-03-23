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
        Signals that the session is live and usable.
        """
        self._connected = True
        self._ready.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=None):
        """
        IBKR error and status channel.
        """
        level = "INFO" if errorCode in (2104, 2106, 2158) else "ERROR"
        print(f"[IBKR][{level}] code={errorCode} msg={errorString}")

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
            _RUNTIME = IBKRRuntime()
        return _RUNTIME

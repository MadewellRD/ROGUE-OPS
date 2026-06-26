#
# market_data_loop.py
#
# Market Data Orchestration Loop
# PHASE 20.3 — MARKET DATA AUTHORITY INTEGRATION
#
# Responsible for:
# - Polling live market data adapters
# - Producing canonical MarketSnapshot objects
# - Respecting OPS halt + kill switch
# - Providing deterministic cadence
#
# Explicitly NOT responsible for:
# - Strategy logic
# - Signal generation
# - Execution
# - Risk decisions
# - State transitions
#

import time
import datetime as dt
from typing import Literal

from kill_switch import kill_active
from ops_state import get_ops_state
from market_data import MarketSnapshot
from market_data_adapter_steady import get_market_snapshot


# ==================================================
# Configuration (HARD, AUTHORITATIVE)
# ==================================================

POLL_INTERVAL_SECONDS = 5

SUPPORTED_SOURCES = {"PAPER", "LIVE"}
SUPPORTED_SYMBOLS = {"SPY", "IWM"}


# ==================================================
# Market Data Loop
# ==================================================

class MarketDataLoop:
    """
    Deterministic market data polling loop.

    This loop is:
    - Side-effect free (except I/O)
    - Replay-safe (adapter swap)
    - Kill-switch aware
    - OPS-halt aware
    """

    def __init__(
        self,
        *,
        symbol: str,
        source: Literal["PAPER", "LIVE"],
        steady_api_key: str,
    ):
        if symbol not in SUPPORTED_SYMBOLS:
            raise RuntimeError(f"Unsupported symbol: {symbol}")

        if source not in SUPPORTED_SOURCES:
            raise RuntimeError(f"Unsupported source: {source}")

        if not steady_api_key:
            raise RuntimeError("Steady API key must be provided")

        self.symbol = symbol
        self.source = source
        self.steady_api_key = steady_api_key

        self.ops = get_ops_state()

        print(
            f"[OK] MarketDataLoop initialized "
            f"(symbol={symbol}, source={source})"
        )

    # --------------------------------------------------
    # Single poll (TESTABLE)
    # --------------------------------------------------

    def poll_once(self) -> MarketSnapshot:
        """
        Fetch a single MarketSnapshot.

        Raises on failure.
        """

        snapshot = get_market_snapshot(
            symbol=self.symbol,
            source=self.source,
            api_key=self.steady_api_key,
        )

        return snapshot

    # --------------------------------------------------
    # Continuous loop
    # --------------------------------------------------

    def run(self) -> None:
        """
        Blocking polling loop.

        Terminates only on:
        - OPS halt
        - Kill switch
        """

        print("[OPS] Market data loop started")

        while True:
            # ------------------------------------------
            # Kill / OPS halt (absolute)
            # ------------------------------------------

            if kill_active() or self.ops.is_halted():
                print("[OPS] Market data loop halted")
                return

            try:
                snapshot = self.poll_once()

                # --------------------------------------
                # EMIT SNAPSHOT (LOG ONLY FOR NOW)
                # --------------------------------------

                print(
                    f"[MARKET] {snapshot.symbol} "
                    f"{snapshot.spot:.2f} "
                    f"{snapshot.session} "
                    f"{snapshot.timestamp_utc.isoformat()}"
                )

            except Exception as e:
                # Fail-closed but do NOT kill OPS
                print(f"[ERROR] Market data polling failure: {e}")

            time.sleep(POLL_INTERVAL_SECONDS)

#
# market/market_data_ibkr_history.py
#
# IBKR historical-bars source for the research/backtest framework.
# Pulls intraday or daily OHLCV via reqHistoricalData and returns the SAME
# Bar objects the research engine already consumes (market_data_massive.Bar),
# so the backtest harness runs unchanged on IBKR intraday data.
#
# Research/offline use — needs TWS/IB Gateway running (paper 7497). Read-only.
# Requires ibapi (imported at module load), so it is NOT part of the SIM/CI suite.
#

import os
import threading
import time
from typing import List, Optional

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

from market.market_data_massive import Bar

# IBKR informational/status codes that are not errors.
_INFO_CODES = {2104, 2106, 2107, 2108, 2119, 2158, 2100, 2150}


class _HistClient(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self._ready = threading.Event()
        self._done = threading.Event()
        self._raw = []
        self.error_msg: Optional[str] = None

    def nextValidId(self, orderId):
        self._ready.set()

    def error(self, reqId, code, msg, advancedOrderRejectJson=""):
        if code in _INFO_CODES:
            return
        self.error_msg = f"{code}: {msg}"
        print(f"[IBKR-HIST][{code}] {msg}")
        # End the wait on hard request errors so we don't block.
        if code in (162, 165, 200, 300, 321, 354, 420, 504, 502):
            self._done.set()

    def historicalData(self, reqId, bar):
        self._raw.append(bar)

    def historicalDataEnd(self, reqId, start, end):
        self._done.set()


def fetch_bars(
    symbol: str,
    *,
    duration: str = "10 D",
    bar_size: str = "5 mins",
    what_to_show: str = "TRADES",
    use_rth: bool = True,
    host: Optional[str] = None,
    port: Optional[int] = None,
    timeout: float = 45.0,
) -> List[Bar]:
    """
    Fetch historical bars from IBKR. Returns market_data_massive.Bar objects
    (t_ms epoch, OHLCV, vwap). `duration` / `bar_size` use IBKR syntax, e.g.
    duration "10 D" / "1 Y", bar_size "1 min" / "5 mins" / "1 day".
    """
    host = host or os.getenv("IBKR_HOST", "127.0.0.1")
    port = port or int(os.getenv("IBKR_PORT", "7497"))

    c = _HistClient()
    c.connect(host, port, clientId=int(time.time()) % 9000 + 200)
    threading.Thread(target=c.run, daemon=True).start()
    if not c._ready.wait(15):
        try:
            c.disconnect()
        finally:
            raise RuntimeError("IBKR connect timeout (TWS up + API enabled on this port?)")

    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"

    # formatDate=2 -> bar.date is epoch seconds (UTC), easiest to normalize.
    c.reqHistoricalData(1, contract, "", duration, bar_size, what_to_show,
                        1 if use_rth else 0, 2, False, [])
    c._done.wait(timeout)

    bars: List[Bar] = []
    for b in c._raw:
        try:
            avg = getattr(b, "average", None)
            bars.append(Bar(
                t_ms=int(b.date) * 1000,
                open=float(b.open), high=float(b.high), low=float(b.low), close=float(b.close),
                volume=float(b.volume), vwap=(float(avg) if avg is not None else None),
            ))
        except (TypeError, ValueError):
            continue

    try:
        c.cancelHistoricalData(1)
    except Exception:
        pass
    c.disconnect()

    if not bars and c.error_msg:
        raise RuntimeError(f"IBKR historical error {c.error_msg}")
    bars.sort(key=lambda x: x.t_ms)
    return bars

#
# tools/ibkr_history_probe.py
#
# Probe what historical/market data this IBKR account actually provides.
# Connects to TWS/Gateway (paper 7497) and:
#   1) requests intraday historical bars for SPY (the 0DTE-research gap),
#   2) requests daily bars,
#   3) enables delayed data and requests an option-chain reference.
# Read-only; places no orders.
#
#   python tools\ibkr_history_probe.py
#

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract


class Probe(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.req_done = {}
        self.bars = {}
        self.chain = []

    def nextValidId(self, orderId):
        self.ready.set()

    def error(self, reqId, code, msg, advancedOrderRejectJson=""):
        if code not in (2104, 2106, 2158, 2107, 2119):
            print(f"[IBKR][{reqId}] {code}: {msg}")

    def historicalData(self, reqId, bar):
        self.bars.setdefault(reqId, []).append(bar)

    def historicalDataEnd(self, reqId, start, end):
        self.req_done.setdefault(reqId, threading.Event()).set()

    def securityDefinitionOptionParameter(self, reqId, exch, underlyingConId, tradingClass, multiplier, expirations, strikes):
        self.chain.append((exch, tradingClass, multiplier, sorted(expirations)[:3], len(strikes)))

    def securityDefinitionOptionParameterEnd(self, reqId):
        self.req_done.setdefault(reqId, threading.Event()).set()


def _spy() -> Contract:
    c = Contract()
    c.symbol = "SPY"; c.secType = "STK"; c.exchange = "SMART"; c.currency = "USD"
    return c


def _wait(p, reqId, timeout):
    ev = p.req_done.setdefault(reqId, threading.Event())
    ev.wait(timeout)


def main() -> None:
    p = Probe()
    p.connect("127.0.0.1", 7497, clientId=int(time.time()) % 9000 + 100)
    threading.Thread(target=p.run, daemon=True).start()
    if not p.ready.wait(15):
        raise SystemExit("Could not connect to TWS on 7497 (is it running + API enabled?)")

    # 1) intraday 5-min bars, last 5 sessions
    p.reqHistoricalData(1, _spy(), "", "5 D", "5 mins", "TRADES", 1, 1, False, [])
    _wait(p, 1, 30)
    print(f"\nINTRADAY 5-min SPY bars: {len(p.bars.get(1, []))}")
    for b in (p.bars.get(1, [])[:2] + p.bars.get(1, [])[-2:]):
        print(f"   {b.date}  O {b.open} H {b.high} L {b.low} C {b.close} V {b.volume}")

    # 2) daily bars, last ~1y
    p.reqHistoricalData(2, _spy(), "", "1 Y", "1 day", "TRADES", 1, 1, False, [])
    _wait(p, 2, 30)
    print(f"\nDAILY SPY bars (1Y): {len(p.bars.get(2, []))}")

    # 3) option chain reference (no market-data subscription needed)
    p.reqSecDefOptParams(3, "SPY", "", "STK", 0)
    _wait(p, 3, 20)
    print(f"\nOPTION CHAIN refs: {len(p.chain)}")
    for exch, tc, mult, exps, nstrikes in p.chain[:4]:
        print(f"   {exch} {tc} x{mult}  expiries~{exps}  strikes={nstrikes}")

    p.disconnect()
    print("\nprobe complete")


if __name__ == "__main__":
    main()

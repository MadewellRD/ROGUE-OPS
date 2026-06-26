#
# tools/ibkr_paper_smoke.py
#
# IBKR live-path smoke test against a LOCAL TWS / IB Gateway (paper by default).
# This is the IBKR analog of tools/robinhood_mcp_probe.py: it verifies the
# real order path that cannot be exercised without a broker session.
#
# Prereqs:
#   - TWS or IB Gateway running locally and logged into a PAPER account
#   - API enabled in TWS (Global Config > API > Enable ActiveX and Socket Clients)
#   - pip install ibapi
#
# Default (SAFE): connectivity + account summary + next order id ONLY. No order.
#
# Run from repo root:
#   python tools\ibkr_paper_smoke.py
#   python tools\ibkr_paper_smoke.py --place --yes                 # 1-share SPY MKT (equity)
#   python tools\ibkr_paper_smoke.py --place --opt --strike 500 --yes   # 1 SPY 0DTE call
#
# Ports: 7497 = paper (default), 7496 = LIVE (the tool refuses --place on 7496
# unless you also pass --allow-live).
#

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PAPER_PORT = 7497
LIVE_PORT = 7496


def _today_expiry() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")


def main() -> None:
    ap = argparse.ArgumentParser(description="IBKR paper smoke test")
    ap.add_argument("--place", action="store_true", help="submit ONE tiny test order")
    ap.add_argument("--opt", action="store_true", help="place an option (default: 1-share equity)")
    ap.add_argument("--strike", type=float, help="option strike (required with --opt)")
    ap.add_argument("--symbol", default="SPY", choices=["SPY", "IWM"])
    ap.add_argument("--yes", action="store_true", help="confirm you intend to place a test order")
    ap.add_argument("--allow-live", action="store_true", help="permit --place on the LIVE port")
    ap.add_argument("--force-mkt", action="store_true", help="force MKT (skip marketable-limit pricing; for no-data testing)")
    args = ap.parse_args()

    if args.force_mkt:
        os.environ["ROGUE_FORCE_MKT"] = "1"

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", str(PAPER_PORT)))
    print(f"Connecting to IBKR at {host}:{port} ({'LIVE' if port == LIVE_PORT else 'paper'}) ...")

    try:
        from broker.ibkr_runtime import get_ibkr_runtime
    except ImportError as e:
        raise SystemExit(f"ibapi not installed: {e}. `pip install ibapi`")

    try:
        runtime = get_ibkr_runtime()
    except Exception as e:
        raise SystemExit(
            f"Could not establish IBKR session ({e}). Is TWS/IB Gateway running, "
            f"logged in, with the API enabled on port {port}?"
        )

    # Give the streaming account summary a moment to populate.
    time.sleep(3)
    print("Connected. Account summary (streamed):")
    for tag in ("NetLiquidation", "AvailableFunds", "ExcessLiquidity", "BuyingPower"):
        print(f"  {tag:18} {runtime._acct_summary.get(tag, '<pending>')}")
    print(f"  next_order_id      {runtime.next_order_id()}")

    if not args.place:
        print("\nConnectivity OK. Re-run with --place --yes to submit a tiny test order.")
        return

    if port == LIVE_PORT and not args.allow_live:
        raise SystemExit("Refusing to place on the LIVE port without --allow-live.")
    if not args.yes:
        raise SystemExit("Add --yes to confirm you intend to place a (paper) test order.")

    from execution.execution_contracts import ExecutionIntent, OptionSpec
    from broker.ibkr_broker import get_ibkr_broker

    if args.opt:
        if args.strike is None:
            raise SystemExit("--opt requires --strike")
        intent = ExecutionIntent.new(
            symbol=args.symbol, qty=1, action="BUY", sec_type="OPT", strategy_tag="SMOKE",
            option=OptionSpec(expiry=_today_expiry(), strike=args.strike, right="C"),
        )
    else:
        intent = ExecutionIntent.new(
            symbol=args.symbol, qty=1, action="BUY", sec_type="STK", strategy_tag="SMOKE",
        )

    print(f"\nSubmitting test order: {intent.sec_type} {intent.symbol} x1 BUY ...")
    result = get_ibkr_broker().execute_intent(intent)
    print(f"Submitted. broker order_id={result.order_id} "
          f"type={result.raw.get('order_type')} limit={result.raw.get('limit_price')} "
          f"fill={result.raw.get('fill_price')}")

    # Poll for acknowledgement / status (or a broker message) for a bit.
    for _ in range(15):
        status = runtime.order_status(result.order_id)
        msg = runtime.order_message(result.order_id)
        if status:
            print(f"order status: {status}")
            break
        if msg:
            print(f"broker message: {msg}")
            break
        time.sleep(1)
    else:
        print("No status/message yet. Check the Orders tab in TWS.")


if __name__ == "__main__":
    main()

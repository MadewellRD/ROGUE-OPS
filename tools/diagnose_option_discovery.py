#
# diagnose_option_discovery.py
#
# IBKR Option Discovery Diagnostic
# PHASE 9A — READ-ONLY DIAGNOSTIC
#
# Purpose:
# - Verify IBKR option chain availability
# - Enumerate REAL 0DTE option contracts
# - Catch sec-def / chain issues BEFORE execution
#
# This file:
# - Does NOT place trades
# - Does NOT modify state
# - Does NOT create intents
#

import datetime as dt

from ibkr_option_discovery import discover_0dte_options


# ----------------------------
# Operator-configurable inputs
# ----------------------------

SYMBOL = "SPY"          # SPY or IWM
DIRECTION = "CALL"      # CALL or PUT
SPOT_PRICE = 475.0      # Approximate spot (filtering only)


def main():
    print("\n[DIAGNOSTIC] IBKR 0DTE OPTION DISCOVERY")
    print(f"  Symbol    : {SYMBOL}")
    print(f"  Direction : {DIRECTION}")
    print(f"  Spot (est): {SPOT_PRICE}")
    print(f"  Date (UTC): {dt.datetime.utcnow().date()}")
    print("\n[QUERY] Requesting option chain from IBKR...\n")

    try:
        contracts = discover_0dte_options(
            symbol=SYMBOL,
            direction=DIRECTION,
            spot=SPOT_PRICE,
        )
    except Exception as e:
        print(f"[ERROR] Discovery failed: {e}")
        return

    print(f"[OK] Discovered {len(contracts)} contracts:\n")

    for c in contracts:
        print(
            f"  {c.symbol} {c.expiry} "
            f"{c.right} {c.strike:<7} "
            f"conId={c.conid} "
            f"class={c.trading_class}"
        )

    print("\n[DIAGNOSTIC COMPLETE]")
    print("If this list is empty or incorrect, DO NOT PROCEED TO EXECUTION.")


if __name__ == "__main__":
    main()

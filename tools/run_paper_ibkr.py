#
# tools/run_paper_ibkr.py
#
# GCP-FREE paper autonomy on IBKR live data.
#
# Unlike `main.py --mode PAPER` (which loads doctrine + secrets from GCS and
# feeds the loop from Steady), this entrypoint needs NEITHER GCP NOR Steady:
#   - live market data comes from IBKR (rolling reqHistoricalData bars),
#   - orders route to IBKR via IBKR_HOST/IBKR_PORT (Gateway paper = 4002),
#   - it runs the same verified SignalEngine -> StateMachine -> execution spine.
#
# It is kill-dominant: an engaged kill file suppresses autonomy on boot.
#
#   # host, IB Gateway paper on localhost:
#   set IBKR_HOST=127.0.0.1 & set IBKR_PORT=4002 & python tools\run_paper_ibkr.py
#   # container (see docker-compose loop service): IBKR_HOST=host.docker.internal
#

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance.bootstrap_env import bootstrap_environment
from governance.kill_switch import kill_active
from ops_config import load_ops_config
from execution.state_machine import StateMachineV2
from market.market_loop import run_market_loop
from market.market_data_ibkr_live import IBKRSnapshotProvider


def main() -> None:
    # PAPER, but with no cloud/broker-secret bootstrap (IBKR is the data + exec).
    os.environ.setdefault("EXECUTION_MODE", "PAPER")
    os.environ.setdefault("OPS_MODE", "PAPER")

    bootstrap_environment()
    ops_config = load_ops_config()

    symbol = os.getenv("PRIMARY_SYMBOL", "SPY")
    account_id = os.getenv("IBKR_ACCOUNT_ID") or "PAPER"
    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = os.getenv("IBKR_PORT", "4002")

    print("\n--- ROGUE:OPS PAPER (IBKR feed, GCP-free) ---")
    print(f"  symbol={symbol}  ibkr={host}:{port}  account={account_id}  mode={ops_config.mode}")

    if kill_active():
        print("[PAPER] Kill active — autonomy suppressed. Clear the kill file and restart to resume.")
        return

    # Start the IBKR runtime up front so its streaming account-summary feed
    # populates the balance store that PAPER position-sizing reads (sizing is
    # balance-aware and fails closed without a fresh balance). Order execution
    # reuses this same singleton connection.
    try:
        from broker.ibkr_runtime import get_ibkr_runtime
        get_ibkr_runtime()
        print(f"[PAPER] IBKR runtime connected ({host}:{port}) — streaming account balance.")
    except Exception as e:
        print(f"[PAPER] IBKR runtime init failed (balance feed unavailable): {e}")

    state_machine = StateMachineV2(ibkr_account_id=account_id)
    provider = IBKRSnapshotProvider(
        symbol,
        source="PAPER",
        bar_size=os.getenv("IBKR_BAR_SIZE", "1 min"),
        duration=os.getenv("IBKR_DURATION", "1 D"),
        refetch_sec=float(os.getenv("IBKR_REFETCH_SEC", "20")),
    )

    run_market_loop(
        ops_config=ops_config,
        primary_symbol=symbol,
        state_machine=state_machine,
        account_id=account_id,
        snapshot_provider=provider,
    )


if __name__ == "__main__":
    main()

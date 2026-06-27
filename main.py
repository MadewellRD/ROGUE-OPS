#
# main.py
#
# ROGUE:OPS application entrypoint (OPS-authoritative bootstrap).
#
# SIM / REPLAY are fully self-contained self-tests: no GCP, no broker, no
# secrets. PAPER / LIVE autonomy now lives in the GCP-free IBKR path:
#
#     python tools/run_paper_ibkr.py        (IB Gateway paper 4002)
#
# main.py intentionally no longer carries the legacy GCP doctrine load or the
# SteadyAPI feed — both were removed when the live feed moved to IBKR.
#

import os
import argparse

from governance.bootstrap_env import bootstrap_environment
from ops_config import load_ops_config
from execution.state_machine import StateMachineV2

# Strategy system (bootstrap only; retained).
from strategy.registry import StrategyRegistry
from strategy.feedback.store import StrategyFeedbackStore


def parse_args():
    parser = argparse.ArgumentParser(description="ROGUE:OPS Entrypoint")
    parser.add_argument("--mode", choices=["REPLAY", "SIM", "PAPER", "LIVE"], help="Override OPS_MODE")
    parser.add_argument("--env", choices=["DEV", "STAGING", "PROD"], help="Override OPS_ENV")
    parser.add_argument("--version", help="Override OPS_VERSION")
    parser.add_argument("--ibkr", help="Override IBKR account ID")
    return parser.parse_args()


def run_application():
    args = parse_args()
    if args.mode:
        os.environ["OPS_MODE"] = args.mode
    if args.env:
        os.environ["OPS_ENV"] = args.env
    if args.version:
        os.environ["OPS_VERSION"] = args.version

    bootstrap_environment()

    print("\n--- ROGUE:OPS Initializing (Authoritative Mode) ---")
    ops_config = load_ops_config()

    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "SIM")
    if EXECUTION_MODE not in ("SIM", "PAPER", "LIVE", "CAPITAL"):
        raise RuntimeError(f"Invalid EXECUTION_MODE: {EXECUTION_MODE}")

    BROKER_ACCOUNT_ID = (
        args.ibkr
        or os.getenv("IBKR_ACCOUNT_ID")
        or os.getenv("ROBINHOOD_ACCOUNT_ID")
        or "SIM"
    )

    print(f"  [OPS_MODE ] {ops_config.mode}")
    print(f"  [OPS_ENV  ] {ops_config.environment}")
    print(f"  [VERSION  ] {ops_config.version}")
    print(f"  [EXECUTE  ] {EXECUTION_MODE}")
    print(f"  [ACCOUNT  ] {BROKER_ACCOUNT_ID}")

    # --------------------------------------------------
    # PAPER / LIVE / CAPITAL autonomy moved out of main.py.
    # The GCP-free IBKR entrypoint is the single live path now.
    # --------------------------------------------------
    if EXECUTION_MODE in ("PAPER", "LIVE", "CAPITAL"):
        print("\n[MOVED] PAPER/LIVE autonomy now runs on the GCP-free IBKR feed:")
        print("    python tools/run_paper_ibkr.py        (IB Gateway paper 4002)")
        print("  main.py supports SIM / REPLAY self-tests only.")
        return

    # --------------------------------------------------
    # SIM / REPLAY self-test (no cloud, no broker, no secrets).
    # --------------------------------------------------
    print("  [OK] SIM/REPLAY mode — GCP, broker, and secrets skipped")

    state_machine = StateMachineV2(ibkr_account_id=BROKER_ACCOUNT_ID)
    _ = state_machine  # constructed to assert the spine wires up cleanly

    registry = StrategyRegistry()
    registry.discover()
    StrategyFeedbackStore()
    print("  [OK] Strategy Registry initialized")
    print("  [OK] Strategy Feedback Store initialized")

    print("\n--- Initialization complete (SIM/REPLAY self-test; no autonomy loop here). ---")


if __name__ == "__main__":
    run_application()

#
# main.py
#
# ROGUE:OPS application entrypoint
# OPS-authoritative bootstrap
#

import os
import argparse
from pathlib import Path

# --------------------------------------------------
# IMPORTS (AUTHORITATIVE ONLY)
# --------------------------------------------------
from governance.bootstrap_env import bootstrap_environment
from governance.gcp_clients import load_doctrine_from_gcs, get_api_keys
from execution.state_machine import StateMachineV2
from ops_config import load_ops_config
from governance.kill_switch import kill_active
from capital.capital_preflight import run_capital_preflight

# Strategy system (BOOTSTRAP ONLY)
from strategy.registry import StrategyRegistry
from strategy.feedback.store import StrategyFeedbackStore

# Vendor health (READ-ONLY)
from market.market_data_adapter_steady import get_market_snapshot
from audit.vendor_health_log import log_vendor_health


# --------------------------------------------------
# CLI ARGUMENTS (TESTING ONLY)
# --------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="ROGUE:OPS Entrypoint")

    parser.add_argument(
        "--mode",
        choices=["REPLAY", "SIM", "PAPER", "LIVE"],
        help="Override OPS_MODE (testing only)",
    )

    parser.add_argument(
        "--env",
        choices=["DEV", "STAGING", "PROD"],
        help="Override OPS_ENV (testing only)",
    )

    parser.add_argument(
        "--version",
        help="Override OPS_VERSION (testing only)",
    )

    parser.add_argument(
        "--ibkr",
        help="Override IBKR account ID (testing only)",
    )

    return parser.parse_args()


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

def run_application():
    args = parse_args()

    # --------------------------------------------------
    # APPLY CLI OVERRIDES
    # --------------------------------------------------
    if args.mode:
        os.environ["OPS_MODE"] = args.mode
    if args.env:
        os.environ["OPS_ENV"] = args.env
    if args.version:
        os.environ["OPS_VERSION"] = args.version

    # --------------------------------------------------
    # ENVIRONMENT BOOTSTRAP
    # --------------------------------------------------
    bootstrap_environment()

    print("\n--- ROGUE:OPS Initializing (Authoritative Mode) ---")

    ops_config = load_ops_config()

    # --------------------------------------------------
    # MODE RESOLUTION
    #
    # SIM and REPLAY are fully self-contained: no GCP, no broker,
    # no credentials. Cloud/broker dependencies are required ONLY
    # for PAPER / LIVE / CAPITAL.
    # --------------------------------------------------
    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "SIM")

    if EXECUTION_MODE not in ("SIM", "PAPER", "LIVE", "CAPITAL"):
        raise RuntimeError(f"Invalid EXECUTION_MODE: {EXECUTION_MODE}")

    sim_like = EXECUTION_MODE == "SIM" or ops_config.mode in ("SIM", "REPLAY")

    BROKER_ACCOUNT_ID = (
        args.ibkr
        or os.getenv("ROBINHOOD_ACCOUNT_ID")
        or os.getenv("IBKR_ACCOUNT_ID")
        or "SIM"
    )

    print(f"  [OPS_MODE ] {ops_config.mode}")
    print(f"  [OPS_ENV  ] {ops_config.environment}")
    print(f"  [VERSION  ] {ops_config.version}")
    print(f"  [EXECUTE  ] {EXECUTION_MODE}")
    print(f"  [ACCOUNT  ] {BROKER_ACCOUNT_ID}")

    steady_api_key = None

    if sim_like:
        print("  [OK] SIM/REPLAY mode — GCP, broker, and secrets skipped")
    else:
        # --------------------------------------------------
        # REQUIRED ENVIRONMENT VARIABLES (CLOUD/BROKER MODES)
        # --------------------------------------------------
        GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
        DOCTRINE_BUCKET = os.getenv("DOCTRINE_BUCKET")
        GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not GCP_PROJECT_ID:
            raise RuntimeError("GCP_PROJECT_ID is not set")
        if not DOCTRINE_BUCKET:
            raise RuntimeError("DOCTRINE_BUCKET is not set")
        if not GOOGLE_CREDENTIALS:
            raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set")

        cred_path = Path(GOOGLE_CREDENTIALS)
        if not cred_path.exists():
            raise RuntimeError(f"Credential file not found: {cred_path}")

        print(f"  [CREDS    ] {cred_path}")

        # --------------------------------------------------
        # LOAD DOCTRINE + SECRETS
        # --------------------------------------------------
        load_doctrine_from_gcs(
            project_id=GCP_PROJECT_ID,
            bucket_name=DOCTRINE_BUCKET,
        )

        api_keys = get_api_keys(
            project_id=GCP_PROJECT_ID,
            secret_names=["openai-api-key", "steadyapi-key"],
        )

        print("  [OK] Doctrine loaded")
        print("  [OK] Secrets retrieved")

        # --------------------------------------------------
        # STEADYAPI HEALTH CHECK
        # --------------------------------------------------
        steady_api_key = api_keys.get("steadyapi-key")

        try:
            get_market_snapshot(
                symbol="SPY",
                source=ops_config.mode,
                api_key=steady_api_key,
            )
            log_vendor_health(
                vendor="STEADYAPI",
                symbol="SPY",
                success=True,
            )
        except Exception as e:
            log_vendor_health(
                vendor="STEADYAPI",
                symbol="SPY",
                success=False,
                reason=str(e),
            )

    # --------------------------------------------------
    # CAPITAL PREFLIGHT
    # --------------------------------------------------
    if EXECUTION_MODE == "CAPITAL":
        print("\n--- CAPITAL PREFLIGHT CHECK ---")
        run_capital_preflight()

    print("\n--- Initialization Complete. Starting OPS Authority. ---")

    # --------------------------------------------------
    # STATE MACHINE (AUTHORITATIVE INSTANCE)
    # --------------------------------------------------
    state_machine = StateMachineV2(
        ibkr_account_id=BROKER_ACCOUNT_ID,
    )

    # --------------------------------------------------
    # STRATEGY SYSTEM BOOTSTRAP
    # --------------------------------------------------
    registry = StrategyRegistry()
    registry.discover()

    StrategyFeedbackStore()

    print("  [OK] Strategy Registry initialized")
    print("  [OK] Strategy Feedback Store initialized")

    # --------------------------------------------------
    # AUTONOMY LOOP (PHASE 7 HOST)
    # --------------------------------------------------
    if ops_config.mode in ("PAPER", "LIVE", "CAPITAL"):
        if kill_active():
            print("[BOOT] Kill active — autonomy suppressed")
            return

        from market.market_loop import run_market_loop

        run_market_loop(
            ops_config=ops_config,
            steady_api_key=steady_api_key,
            strategy_registry=registry,
            primary_symbol="SPY",
            state_machine=state_machine,
            account_id=BROKER_ACCOUNT_ID,
        )
        return


if __name__ == "__main__":
    run_application()

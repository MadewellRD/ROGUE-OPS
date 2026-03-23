#
# market_loop.py
#
# Market Autonomy Loop
# PHASE 7 — MARKET HOST (LAW-AWARE, NO EXECUTION AUTHORITY)
#

import time
import datetime as dt
from typing import Optional

from ops_config import OPSConfig
from governance.kill_switch import kill_active, engage_kill

from market.market_data_adapter_steady import get_market_snapshot
from market.types.market_snapshot import MarketSnapshot

from advisory.indicator_authority import IndicatorAssertion
from advisory.indicator_engine import IndicatorEngine

from strategy.registry import StrategyRegistry
from strategy.council.council_engine import StrategyCouncilEngine

from arbitration.arbitration_engine import DeterministicArbitrationEngine
from execution.intent_router import IntentRouter
from execution.state_machine import StateMachineV2

from audit.strategy_audit_log import log_market_snapshot


# ==================================================
# MARKET LOOP (HOST ONLY)
# ==================================================

def run_market_loop(
    *,
    ops_config: OPSConfig,
    steady_api_key: str,
    strategy_registry: StrategyRegistry,
    primary_symbol: Optional[str],
    state_machine: StateMachineV2,
    account_id: str,
) -> None:
    """
    Market runtime host.

    Responsibilities:
    - Acquire market data
    - Build immutable MarketSnapshot
    - Invoke council + arbitration
    - Route intents through LAW

    This loop has NO execution authority.
    """

    indicator_engine = IndicatorEngine()
    council_engine = StrategyCouncilEngine(registry=strategy_registry)
    arbitration_engine = DeterministicArbitrationEngine()

    router = IntentRouter(
        state_machine=state_machine,
        account_id=account_id,
        execution_mode=ops_config.mode,
    )

    iteration = 0

    print("\n--- ROGUE MARKET RUNTIME STARTED (PHASE 7) ---")

    try:
        while True:
            if kill_active():
                return

            iteration += 1
            now = dt.datetime.now(dt.timezone.utc)

            # ----------------------------------
            # HEARTBEAT (LIVENESS)
            # ----------------------------------
            print(
                f"[HEARTBEAT][PHASE7] "
                f"iter={iteration} "
                f"ts={now.isoformat()}"
            )

            # ----------------------------------
            # MARKET SNAPSHOT
            # ----------------------------------
            raw = get_market_snapshot(
                symbol=primary_symbol,
                source=ops_config.mode,
                api_key=steady_api_key,
            )

            snapshot = MarketSnapshot(
                snapshot_id=f"{primary_symbol}-{now.isoformat()}",
                timestamp_utc=now,
                session=raw.session,
                primary_symbol=primary_symbol,
                spot=raw.spot,
                raw_primary=raw,
            )

            log_market_snapshot(snapshot)

            # ----------------------------------
            # INDICATORS (AUTHORITATIVE)
            # ----------------------------------
            indicator_assertion = indicator_engine.update(raw)
            if not isinstance(indicator_assertion, IndicatorAssertion):
                engage_kill(reason="Indicator authority violation")
                return

            # ----------------------------------
            # STRATEGY COUNCIL (PHASE 4)
            # ----------------------------------
            council_result = council_engine.evaluate(
                snapshot=snapshot
            )

            # ----------------------------------
            # ARBITRATION (PHASE 5)
            # ----------------------------------
            arbitration_result = arbitration_engine.arbitrate(
                council_result=council_result
            )

            # ----------------------------------
            # ROUTING (PHASE 7)
            # ----------------------------------
            router.route(
                arbitration_result=arbitration_result,
                snapshot=snapshot,
            )

            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        print("[MARKET LOOP] Shutdown signal received. Exiting cleanly.")
        return

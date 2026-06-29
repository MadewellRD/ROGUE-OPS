#
# market_loop.py
#
# Market Autonomy Loop — SignalEngine path
#
# Drives the verified execution spine on live/paper market data:
#   market snapshot -> indicators -> SignalEngine -> StateMachine -> execution
# with exit supremacy (open positions are managed/exited before new entries).
#
# This loop has NO strategy/council/arbitration dependency: per the Phase 3
# decision, the SignalEngine path is the single live decision path. The loop
# itself has no execution authority — the StateMachine authorizes and the
# execution driver executes.
#

import time
from typing import Optional

from ops_config import OPSConfig
from governance.kill_switch import kill_active, engage_kill

from advisory.indicator_authority import IndicatorAssertion
from advisory.indicator_engine import IndicatorEngine
from advisory.signal_engine import SignalEngine

from execution.state_machine import StateMachineV2, SystemState
from execution.execution_driver import execute_and_apply
from execution.position_store import get_position_store


# ==================================================
# Single decision cycle (extracted for testability)
# ==================================================

def market_step(
    *,
    snapshot,
    indicators: IndicatorAssertion,
    signal_engine: SignalEngine,
    state_machine: StateMachineV2,
    positions,
    account_id: str,
    execution_mode: str,
) -> str:
    """
    Run one decision cycle against a snapshot + indicators.

    Returns a short status: EXIT | HOLD | ENTRY | ENTRY_DENIED | ENTRY_FAILED | NO_SIGNAL.
    No network, no sleep — safe to drive directly from tests.
    """

    # --------------------------------------------------
    # EXIT SUPREMACY — manage an open position first.
    # --------------------------------------------------
    if positions.has_open_position():
        if state_machine.state == SystemState.MANAGING_POSITION:
            exit_env = state_machine.manage_position(
                snapshot=snapshot,
                indicators=indicators.required,
                execution_mode=execution_mode,
            )
            if exit_env is not None:
                execute_and_apply(
                    envelope=exit_env,
                    state_machine=state_machine,
                    account_id=account_id,
                )
                return "EXIT"
        return "HOLD"

    # --------------------------------------------------
    # ENTRY — only when flat.
    # --------------------------------------------------
    result = signal_engine.evaluate(snapshot=snapshot, indicators=indicators)
    if result is None:
        return "NO_SIGNAL"

    intent, _context = result

    try:
        entry_env = state_machine.authorize_entry(
            intent=intent,
            snapshot=snapshot,
            execution_mode=execution_mode,
        )
    except Exception as e:
        print(f"[MARKET LOOP] entry not authorized: {e}")
        return "ENTRY_DENIED"

    ok = execute_and_apply(
        envelope=entry_env,
        state_machine=state_machine,
        account_id=account_id,
    )
    return "ENTRY" if ok else "ENTRY_FAILED"


# ==================================================
# MARKET LOOP (HOST)
# ==================================================

def run_market_loop(
    *,
    ops_config: OPSConfig,
    primary_symbol: Optional[str],
    state_machine: StateMachineV2,
    account_id: str,
    snapshot_provider,
    strategy_registry=None,   # retained for call-site compatibility (unused)
) -> None:
    """
    Market runtime host. Acquires data, computes indicators, and runs one
    market_step per cycle. Kill-dominant.

    Data source: `snapshot_provider` is REQUIRED — a callable(symbol) ->
    MarketSnapshot | None, where None means "no new bar this cycle" (skip). The
    legacy SteadyAPI feed was removed; the live feed is IBKR (see
    market_data_ibkr_live.IBKRSnapshotProvider). With no provider the loop fails
    closed (engages kill) rather than run blind.
    """

    indicator_engine = IndicatorEngine()
    signal_engine = SignalEngine()
    positions = get_position_store()
    symbol = primary_symbol or "SPY"
    execution_mode = ops_config.mode

    # Seed-warmup: feed the session's prior bars through the IndicatorEngine now
    # so a freshly (re)started loop is warm and can act on the very next live
    # bar, instead of waiting ~35 minutes for indicators to warm in real time.
    # The hook is optional (getattr) and fail-soft, so SIM/replay providers that
    # don't expose it are unaffected. The provider leaves the latest bar for the
    # live loop, so nothing is double-counted.
    _warmup = getattr(snapshot_provider, "warmup_snapshots", None)
    if callable(_warmup):
        try:
            seeds = _warmup()
            for _s in seeds:
                indicator_engine.update(_s)
            if seeds:
                print(f"[MARKET LOOP] indicator seed-warmup: {len(seeds)} bars")
        except Exception as e:
            print(f"[MARKET LOOP] seed-warmup skipped: {e}")

    print("\n--- ROGUE MARKET RUNTIME STARTED (SignalEngine path) ---")
    iteration = 0

    try:
        while True:
            if kill_active():
                print("[MARKET LOOP] Kill active — exiting.")
                return

            iteration += 1

            if snapshot_provider is None:
                # Steady was removed; the loop requires an injected live feed
                # (see tools/run_paper_ibkr.py). Fail closed rather than run blind.
                engage_kill(reason="NO_SNAPSHOT_PROVIDER")
                print("[MARKET LOOP] No snapshot_provider — fail-closed halt.")
                return
            snapshot = snapshot_provider(symbol)
            if snapshot is None:
                try:
                    from api.terminal_state import publish_state_file
                    publish_state_file()  # heartbeat: keep the console's view fresh between bars
                except Exception:
                    pass
                time.sleep(1)
                continue  # no new bar yet — do not advance indicators

            indicators = indicator_engine.update(snapshot)
            if not isinstance(indicators, IndicatorAssertion):
                engage_kill(reason="INDICATOR_AUTHORITY_VIOLATION")
                return

            status = market_step(
                snapshot=snapshot,
                indicators=indicators,
                signal_engine=signal_engine,
                state_machine=state_machine,
                positions=positions,
                account_id=account_id,
                execution_mode=execution_mode,
            )

            # Surface live state to the operator terminal (best-effort).
            try:
                from api.terminal_state import publish_frame
                publish_frame(snapshot=snapshot, indicators=indicators, signal_status=status)
            except Exception:
                pass

            # Optional SHADOW LLM read (OFF unless OLLAMA_SHADOW=1). Runs on a
            # daemon thread, throttled + single-flight, logged only. It is fully
            # isolated and can never affect this loop's decision, result, or timing.
            try:
                from advisory.shadow_runner import maybe_shadow
                maybe_shadow(
                    symbol=symbol,
                    spot=getattr(snapshot, "spot", None),
                    session=getattr(snapshot, "session", "REGULAR"),
                    req=indicators.required,
                    vwap=(getattr(indicators, "advisory", {}) or {}).get("VWAP"),
                    det_signal=status,
                    det_passed=indicators.required_passed,
                )
            except Exception:
                pass

            print(f"[HEARTBEAT] iter={iteration} status={status} spot={snapshot.spot}")
            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        print("[MARKET LOOP] Shutdown signal received. Exiting cleanly.")
        return

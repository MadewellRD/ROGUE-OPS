#
# tools/test_market_loop.py
#
# Integration test for the SignalEngine live-loop spine (SIM execution).
# Proves the entry->manage->exit lifecycle the system never had wired:
#   - a valid signal produces a sized ENTRY and opens a position
#   - an overbought reading drives manage_position -> EXIT and closes it
#   - the state machine returns to IDLE
#
# No broker, no network. Run from repo root:
#   python tools\test_market_loop.py
#

import os
import sys
import datetime as dt
from pathlib import Path

os.environ.update(
    OPS_MODE="SIM", OPS_ENV="DEV", OPS_VERSION="0.0.0-sim", EXECUTION_MODE="SIM",
)
os.environ.setdefault("ROGUE_OPS_HOME", "/tmp/h")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data import MarketSnapshot
from advisory.signal_engine import SignalEngine
from advisory.indicator_authority import create_indicator_assertion
from execution.state_machine import StateMachineV2, SystemState
from execution.position_store import get_position_store
from market.market_loop import market_step


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="SPY", spot=500.00, session="REGULAR",
        timestamp_utc=dt.datetime(2026, 6, 25, 15, 0, 0, tzinfo=dt.timezone.utc),
        source="SIM",
    )


def _indicators(rsi7: float):
    return create_indicator_assertion(required={
        "VWAP_Position": "above",
        "EMA(9)": 499.5, "EMA(21)": 498.0,
        "RSI(7)": rsi7, "RSI(14)": 52.0, "MACD_Histogram": 0.30,
        "ATR": 1.25,
    })


def main() -> None:
    sm = StateMachineV2(ibkr_account_id="SIM")
    positions = get_position_store()
    signal_engine = SignalEngine()

    assert not positions.has_open_position(), "must start flat"
    assert sm.state == SystemState.IDLE

    # 1) Calm reading -> entry
    status = market_step(
        snapshot=_snapshot(), indicators=_indicators(rsi7=55.0),
        signal_engine=signal_engine, state_machine=sm,
        positions=positions, account_id="SIM", execution_mode="SIM",
    )
    assert status == "ENTRY", f"expected ENTRY, got {status}"
    assert positions.has_open_position(), "position should be open"
    assert sm.state == SystemState.MANAGING_POSITION

    # 2) Overbought reading -> managed exit
    status = market_step(
        snapshot=_snapshot(), indicators=_indicators(rsi7=75.0),
        signal_engine=signal_engine, state_machine=sm,
        positions=positions, account_id="SIM", execution_mode="SIM",
    )
    assert status == "EXIT", f"expected EXIT, got {status}"
    assert not positions.has_open_position(), "position should be closed"
    assert sm.state == SystemState.IDLE, "state machine should return to IDLE"

    print("MARKET LOOP PASS — signal->sized entry->managed exit, full lifecycle, back to IDLE")


if __name__ == "__main__":
    main()

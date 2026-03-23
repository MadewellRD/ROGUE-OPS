# test_engine_and_execution.py

import pytest
from datetime import datetime
from types import SimpleNamespace

from rogueops.advisory.signal_engine import SignalEngine
from rogueops.execution.execution_driver import execute_and_apply

# Mocks / minimal stubs for inputs
class FakeSnapshot:
    def __init__(self, symbol="SPY", session="REGULAR", spot=430.0, source="TEST"):
        self.symbol = symbol
        self.session = session
        self.spot = spot
        self.timestamp_utc = datetime.utcnow()
        self.source = source

class FakeIndicators:
    def __init__(self, keys):
        self.required = {k: 1.0 for k in keys}

class FakeStateMachine:
    def __init__(self):
        self.history = []

class FakeEnvelope:
    def __init__(self, action="ENTRY"):
        self.action = action
        self.id = "ENV123"

# Monkeypatches for execute() and bridge
@pytest.fixture
def patch_execution(monkeypatch):
    monkeypatch.setattr("execution.execution_router.execute", lambda e, a: {"status": "ok"})

    class DummyBridge:
        def __init__(self, state_machine): self.sm = state_machine
        def handle_entry(self, envelope, fill_price, result): self.sm.history.append("entry")
        def handle_exit(self, envelope, result): self.sm.history.append("exit")

    monkeypatch.setattr("execution.execution_position_bridge.ExecutionPositionBridge", DummyBridge)
    monkeypatch.setattr("capital.daily_loss_governor.record_realized_pnl", lambda account_id, envelope: None)


def test_signal_engine_all_indicators_pass():
    engine = SignalEngine()
    snapshot = FakeSnapshot()
    indicators = FakeIndicators(keys=[
        "VWAP_Position", "EMA(9)", "EMA(21)", "RSI(7)", "RSI(14)", "MACD_Histogram", "ATR"
    ])

    result = engine.evaluate(snapshot=snapshot, indicators=indicators)
    assert result is not None, "Expected signal to be emitted"
    intent, context = result
    assert intent.symbol == "SPY"
    assert "indicator_presence" in context["rules_passed"]


def test_signal_engine_missing_indicators():
    engine = SignalEngine()
    snapshot = FakeSnapshot()
    indicators = FakeIndicators(keys=["EMA(9)", "RSI(7)"])  # Incomplete set

    result = engine.evaluate(snapshot=snapshot, indicators=indicators)
    assert result is None, "Expected rejection due to missing indicators"


def test_execute_and_apply_entry_success(patch_execution):
    envelope = FakeEnvelope(action="ENTRY")
    sm = FakeStateMachine()
    result = execute_and_apply(
        envelope=envelope,
        state_machine=sm,
        account_id="TEST123",
        entry_price=430.0
    )
    assert result is True
    assert "entry" in sm.history


def test_execute_and_apply_exit_success(patch_execution):
    envelope = FakeEnvelope(action="EXIT")
    sm = FakeStateMachine()
    result = execute_and_apply(
        envelope=envelope,
        state_machine=sm,
        account_id="TEST123"
    )
    assert result is True
    assert "exit" in sm.history


def test_execute_and_apply_missing_entry_price(patch_execution):
    envelope = FakeEnvelope(action="ENTRY")
    sm = FakeStateMachine()
    result = execute_and_apply(
        envelope=envelope,
        state_machine=sm,
        account_id="TEST123",
        entry_price=None  # Missing on purpose
    )
    assert result is False

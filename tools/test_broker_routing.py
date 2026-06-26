#
# tools/test_broker_routing.py
#
# Capability-routing tests for the multi-broker boundary.
# No broker SDK required (asserts routing + fail-closed guards only).
#
# Run from repo root:
#   python tools\test_broker_routing.py        (Windows)
#   python tools/test_broker_routing.py        (macOS/Linux)
#

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from execution.execution_contracts import ExecutionIntent, OptionSpec
from broker.broker_runtime import get_broker_runtime, BrokerCapabilityError


def _opt() -> ExecutionIntent:
    return ExecutionIntent.new(
        symbol="SPY", qty=1, action="BUY", sec_type="OPT", strategy_tag="test",
        option=OptionSpec(expiry="20260626", strike=500.0, right="C"),
    )


def _stk() -> ExecutionIntent:
    return ExecutionIntent.new(
        symbol="SPY", qty=1, action="BUY", sec_type="STK", strategy_tag="test",
    )


def _clear_env():
    os.environ.pop("BROKER", None)
    os.environ.pop("EQUITY_BROKER", None)


def main() -> None:
    _clear_env()
    assert get_broker_runtime(_opt()).name == "IBKR", "options must default to IBKR"
    assert get_broker_runtime(_stk()).name == "ROBINHOOD", "equities must default to Robinhood"

    # Fail-closed: options must NEVER route to a broker that can't trade them.
    os.environ["BROKER"] = "ROBINHOOD"
    try:
        get_broker_runtime(_opt())
        raise AssertionError("options on Robinhood should have been blocked")
    except BrokerCapabilityError:
        pass

    os.environ["BROKER"] = "IBKR"
    assert get_broker_runtime(_stk()).name == "IBKR"
    assert get_broker_runtime(_opt()).name == "IBKR"

    _clear_env()
    print("BROKER ROUTING PASS — capability routing + fail-closed guards intact")


if __name__ == "__main__":
    main()

#
# broker/broker_runtime.py
#
# Broker Access Boundary (MULTI-BROKER)
#
# This module is the SINGLE seam between the OPS execution layer and any
# concrete broker. execution_router talks ONLY to this boundary — never to a
# broker SDK directly. Concrete backends (IBKR, Robinhood, ...) implement the
# BrokerRuntime Protocol and are selected by configuration + instrument
# capability.
#
# Design rules:
# - Imports are SIM-safe: no broker SDK is imported at module load. Concrete
#   backends are imported lazily inside get_broker_runtime().
# - Routing is FAIL-CLOSED: if the selected broker cannot trade the instrument
#   (e.g. options on Robinhood today), we raise rather than silently mis-route.
#

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from execution.execution_contracts import ExecutionIntent


# ==================================================
# Normalized broker result
# ==================================================

@dataclass(frozen=True)
class BrokerOrderResult:
    """
    What every broker returns and what execution_router records.
    order_id is the broker's order identifier; raw is the broker-native payload.
    """
    order_id: int
    raw: Dict[str, Any] = field(default_factory=dict)


# ==================================================
# Broker Protocol
# ==================================================

@runtime_checkable
class BrokerRuntime(Protocol):
    name: str

    def supports(self, intent: ExecutionIntent) -> bool:
        """True iff this broker can place this instrument/intent TODAY."""
        ...

    def execute_intent(
        self,
        intent: ExecutionIntent,
        override_quantity: Optional[int] = None,
    ) -> BrokerOrderResult:
        ...


class BrokerCapabilityError(RuntimeError):
    """Raised (fail-closed) when a broker is asked to trade an unsupported instrument."""


# ==================================================
# Backend selection
# ==================================================

def _select_backend_name(intent: ExecutionIntent) -> str:
    """
    Resolve which backend should handle an intent.

    Precedence:
      1. BROKER env var (explicit override: IBKR | ROBINHOOD)
      2. Capability default:
           - options  -> IBKR      (only options-capable broker today)
           - equities -> EQUITY_BROKER env (default ROBINHOOD)
    """
    forced = os.getenv("BROKER")
    if forced:
        return forced.upper()

    if intent.sec_type == "OPT":
        return "IBKR"

    return os.getenv("EQUITY_BROKER", "ROBINHOOD").upper()


def get_broker_runtime(intent: ExecutionIntent) -> BrokerRuntime:
    """
    Resolve the broker backend for an intent. Concrete implementations are
    imported lazily so this module (and SIM) never require a broker SDK.

    Fail-closed: raises BrokerCapabilityError if the selected broker cannot
    trade the requested instrument.
    """
    name = _select_backend_name(intent)

    if name == "IBKR":
        from broker.ibkr_broker import get_ibkr_broker
        broker: BrokerRuntime = get_ibkr_broker()
    elif name == "ROBINHOOD":
        from broker.robinhood_broker import get_robinhood_broker
        broker = get_robinhood_broker()
    else:
        raise BrokerCapabilityError(f"Unknown broker backend: {name!r}")

    if not broker.supports(intent):
        raise BrokerCapabilityError(
            f"Broker {broker.name} cannot trade sec_type={intent.sec_type} "
            f"(symbol={intent.symbol}). Routing blocked (fail-closed)."
        )

    return broker

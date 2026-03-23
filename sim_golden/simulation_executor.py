"""
Simulation Executor
PHASE 6 — Golden Path Simulation Sink

This module records simulated execution of authorized intents.

Simulation is:
- Always enabled
- Deterministic
- Replay-safe
- Non-executing

Simulation exists to:
- Validate LAW behavior
- Preserve intent → outcome lineage
- Enable offline analysis and replay
"""

import datetime as dt
from typing import Any

from audit.simulation_audit_log import log_simulation_event


def simulate_authorized_intent(
    *,
    intent: Any,
    source_strategy: str,
) -> None:
    """
    Simulate an authorized intent.

    This function:
    - Does NOT place trades
    - Does NOT touch broker
    - Does NOT mutate capital
    """

    log_simulation_event(
        timestamp_utc=dt.datetime.utcnow().isoformat(),
        intent=intent,
        source_strategy=source_strategy,
        note="Simulated execution (golden path)",
    )

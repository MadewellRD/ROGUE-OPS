"""
Simulation Audit Log
PHASE 6 — Simulation Lineage Recording

Records simulated execution events for replay,
analysis, and validation.

Simulation audit logs:
- Do NOT imply execution
- Do NOT mutate state
- Are strictly informational
"""

from typing import Any
import json
import datetime as dt


def log_simulation_event(
    *,
    timestamp_utc: str,
    intent: Any,
    source_strategy: str,
    note: str,
) -> None:
    """
    Record a simulated execution event.

    This function is:
    - Side-effect safe
    - Deterministic
    - Audit-only
    """

    record = {
        "timestamp_utc": timestamp_utc,
        "source_strategy": source_strategy,
        "intent": repr(intent),
        "note": note,
    }

    # For now, emit to stdout.
    # This preserves determinism and avoids I/O side effects.
    print("[SIMULATION][AUDIT]", json.dumps(record))

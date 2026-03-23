#
# execution_counter_log.py
#
# Execution & Simulation Counters
# PHASE 7.3 — ROUTING OBSERVABILITY (NON-AUTHORITATIVE)
#
# Append-only. Fire-and-forget. Failure-tolerant.
#
# Purpose:
# - Count simulation invocations
# - Count execution attempts
# - Count execution blocks
# - Count kill-switch suppressions
#

import json
import os
import datetime as dt
from typing import Dict, Any

AUDIT_DIR = "/opt/rogueops/audit"
AUDIT_FILE = os.path.join(AUDIT_DIR, "execution_counters.jsonl")


def _write(record: Dict[str, Any]) -> None:
    """
    Best-effort append-only write.
    Must NEVER raise.
    """
    try:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        # Observability must never affect execution
        pass


def log_counter(
    *,
    event: str,
    intent_type: str | None,
    strategy_id: str | None,
) -> None:
    _write({
        "type": "EXECUTION_COUNTER",
        "ts_utc": dt.datetime.utcnow().isoformat(),
        "event": event,
        "intent_type": intent_type,
        "strategy_id": strategy_id,
    })

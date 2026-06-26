#
# execution_telemetry_log.py
#
# Execution Telemetry Sink
# PHASE 9 — OBSERVABILITY (NON-AUTHORITATIVE)
#
# Append-only, failure-tolerant counters for execution flow.
#

import json
import os
import datetime as dt
from typing import Dict, Any

from governance.paths import audit_dir, ensure_dir

AUDIT_FILENAME = "execution_telemetry.jsonl"


def _write(record: Dict[str, Any]) -> None:
    try:
        d = ensure_dir(audit_dir())
        with open(d / AUDIT_FILENAME, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        # Telemetry must never affect runtime behavior
        pass


def log_event(
    *,
    event: str,
    intent_type: str | None,
    strategy: str | None,
    execution_mode: str | None,
    reason: str | None = None,
) -> None:
    _write({
        "ts_utc": dt.datetime.utcnow().isoformat(),
        "event": event,
        "intent_type": intent_type,
        "strategy": strategy,
        "execution_mode": execution_mode,
        "reason": reason,
    })

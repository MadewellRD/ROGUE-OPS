#
# arbitration_audit_log.py
#
# Arbitration Observability Sink
# PHASE 7.2 — ARBITRATION DECISION JOURNAL (NON-AUTHORITATIVE)
#
# Append-only. Fire-and-forget. Failure-tolerant.
#
# Purpose:
# - Log arbitration inputs
# - Log deterministic resolution
# - Explicitly record NO-ACTION cases
#

import json
import os
import datetime as dt
from typing import Any, Dict, List

from governance.paths import audit_dir, ensure_dir

AUDIT_FILENAME = "arbitration_audit.jsonl"


def _write(record: Dict[str, Any]) -> None:
    """
    Best-effort append-only write.
    Must NEVER raise.
    """
    try:
        d = ensure_dir(audit_dir())
        with open(d / AUDIT_FILENAME, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        # Observability must never affect execution
        pass


def log_arbitration_decision(
    *,
    snapshot_id: str | None,
    proposals: List[Any],
    result: Any,
) -> None:
    """
    Log a single arbitration decision.
    """
    _write({
        "type": "ARBITRATION_DECISION",
        "ts_utc": dt.datetime.utcnow().isoformat(),
        "snapshot_id": snapshot_id,
        "proposal_count": len(proposals),
        "proposals": [
            {
                "strategy_id": getattr(p, "strategy_name", None),
                "intent_type": type(p.intent).__name__,
                "intent_repr": repr(p.intent),
            }
            for p in proposals
        ],
        "result": {
            "winning_strategy": getattr(result, "winning_strategy", None),
            "intent_type": (
                type(result.intent).__name__
                if getattr(result, "intent", None) is not None
                else None
            ),
            "reason": getattr(result, "reason", None),
        },
    })

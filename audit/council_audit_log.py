#
# council_audit_log.py
#
# Strategy Council Observability Sink
# PHASE 7.1 — COUNCIL AUDIT LOGGING (NON-AUTHORITATIVE)
#
# Append-only. Fire-and-forget. Failure-tolerant.
#
# Purpose:
# - Log every council proposal
# - Preserve disagreement
# - Enable deterministic replay
#

import json
import os
import datetime as dt
from typing import Any, Dict, List

AUDIT_DIR = "/opt/rogueops/audit"
AUDIT_FILE = os.path.join(AUDIT_DIR, "council_audit.jsonl")


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


def log_council_cycle(
    *,
    snapshot_id: str,
    proposals: List[Any],
) -> None:
    """
    Log a single council evaluation cycle.

    proposals:
        List of CouncilProposal objects (unmodified).
    """
    _write({
        "type": "COUNCIL_CYCLE",
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
    })

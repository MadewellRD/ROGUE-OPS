#
# strategy_audit_log.py
#
# Strategy + Market Observability Sink
# PHASE 59 — AUDIT LOGGING (NON-AUTHORITATIVE)
#
# Append-only. Fire-and-forget. Failure-tolerant.
#

import json
import os
import datetime as dt
from typing import Dict, Any

AUDIT_DIR = "/opt/rogueops/audit"
AUDIT_FILE = os.path.join(AUDIT_DIR, "strategy_audit.jsonl")


def _write(record: Dict[str, Any]) -> None:
    """
    Best-effort append-only write.
    Never raises.
    """
    try:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        # Audit failure must NEVER affect execution
        pass


def log_market_snapshot(snapshot) -> None:
    _write({
        "type": "MARKET_SNAPSHOT",
        "ts_utc": dt.datetime.utcnow().isoformat(),
        "snapshot_id": snapshot.snapshot_id,
        "session": snapshot.session,
        "primary_symbol": snapshot.primary_symbol,
        "spot": snapshot.spot,
    })


def log_strategy_evaluation(
    *,
    snapshot_id: str,
    strategy_id: str,
    decision: str,
    metadata: Dict[str, Any] | None = None,
) -> None:
    _write({
        "type": "STRATEGY_EVALUATION",
        "ts_utc": dt.datetime.utcnow().isoformat(),
        "snapshot_id": snapshot_id,
        "strategy_id": strategy_id,
        "decision": decision,
        "metadata": metadata or {},
    })

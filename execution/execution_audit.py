#
# execution_audit.py
#
# Execution Audit & Forensics
# PHASE 16 + PHASE 27 — JUSTIFICATION-AWARE (ATOMIC)
#
# Responsible for:
# - Constructing immutable execution audit records
# - Hash-linking execution artifacts
# - Persisting cryptographic justification references
# - Providing forensic-grade traceability
#
# Explicitly NOT responsible for:
# - Persistence
# - Execution logic
# - Risk decisions
#

import hashlib
import json
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Any


# ----------------------------
# Deterministic hashing
# ----------------------------

def _stable_hash(payload: Dict[str, Any]) -> str:
    """
    Produce a deterministic SHA-256 hash from a dict.
    """
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ----------------------------
# Audit Record
# ----------------------------

@dataclass(frozen=True)
class AuditRecord:
    """
    Immutable execution audit record.
    """

    record_type: str
    payload: Dict[str, Any]
    created_at_utc: dt.datetime
    record_hash: str


# ----------------------------
# Canonical constructor
# ----------------------------

def create_audit_record(
    *,
    record_type: str,
    payload: Dict[str, Any],
) -> AuditRecord:
    """
    Create an immutable audit record.

    This function is the ONLY way audit records
    may be constructed.
    """

    created_at = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
    )

    materialized = {
        "record_type": record_type,
        "payload": payload,
        "created_at_utc": created_at.isoformat(),
    }

    record_hash = _stable_hash(materialized)

    return AuditRecord(
        record_type=record_type,
        payload=payload,
        created_at_utc=created_at,
        record_hash=record_hash,
    )


# ----------------------------
# Execution audit hook
# ----------------------------

def log_execution_event(
    mode: str,
    envelope,
    result,
) -> None:
    """
    Execution audit hook.

    Phase 27:
    - Cryptographically binds SignalContext via hash only
    - No strategy leakage
    """

    payload = {
        "mode": mode,
        "envelope_hash": envelope.envelope_hash,
        "signal_context_hash": envelope.intent.signal_context_hash,
        "intent": envelope.intent.to_dict(),
        "result": {
            "status": result.status,
            "order_id": result.order_id,
            "reason": result.reason,
            "executed_utc": result.executed_utc,
        },
    }

    record = create_audit_record(
        record_type="EXECUTION_EVENT",
        payload=payload,
    )

    # Phase-16 compatible stdout emission
    print(
        "\n[EXECUTION AUDIT]"
        f"\n  time: {record.created_at_utc.isoformat()}"
        f"\n  type: {record.record_type}"
        f"\n  hash: {record.record_hash}"
        f"\n  payload: {json.dumps(record.payload, indent=2)}\n"
    )

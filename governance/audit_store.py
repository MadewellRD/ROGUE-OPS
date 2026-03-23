#
# governance/audit_store.py
#
# Audit Store Authority — Immutable, Ordered, Kill-Aware
# PHASE 22 + PHASE 36c — SOC-DEFENSIBLE (ATOMIC)
#
# Guarantees:
# - Append-only semantics
# - Deterministic ordering
# - Hash chaining (tamper-evident)
# - Kill-context capture
#
# Phase 36c:
# - Optional, non-blocking Capital Shadow observation
#
# Explicitly NOT responsible for:
# - Record construction
# - Execution logic
# - Risk decisions
# - Shadow enforcement
#

from typing import List, Optional
import hashlib
import json

from execution.execution_audit import AuditRecord
from governance.kill_switch import kill_context

# Phase 36 — OPTIONAL shadow observer
try:
    from capital.capital_shadow_engine import CapitalShadowEngine
except Exception:
    CapitalShadowEngine = None  # Shadow mode fully suppressible


class AuditStore:
    """
    Immutable, append-only audit store.

    This store provides SOC-grade guarantees:
    - Total order
    - Hash chaining
    - Kill-state attribution
    """

    def __init__(self):
        self._records: List[dict] = []
        self._last_hash: Optional[str] = None
        self._seq: int = 0

        # Phase 36 — Shadow observer (optional)
        self._shadow_engine = (
            CapitalShadowEngine() if CapitalShadowEngine else None
        )

    # --------------------------------------------------
    # Append (ONLY MUTATION PATH)
    # --------------------------------------------------

    def append(self, record: AuditRecord) -> None:
        """
        Append an audit record with ordering, chaining,
        kill-context capture, and optional shadow observation.
        """

        envelope = {
            "seq": self._seq,
            "record_hash": record.record_hash,
            "prev_hash": self._last_hash,
            "record_type": record.record_type,
            "payload": record.payload,
            "created_at_utc": record.created_at_utc.isoformat(),
            "kill_context": kill_context(),
        }

        envelope_hash = self._hash(envelope)

        persisted = {
            **envelope,
            "envelope_hash": envelope_hash,
        }

        # ----------------------------
        # Persist (authoritative)
        # ----------------------------

        self._records.append(persisted)
        self._last_hash = envelope_hash
        self._seq += 1

        # ----------------------------
        # Phase 36 — Shadow observe (NON-BLOCKING)
        # ----------------------------

        if self._shadow_engine:
            try:
                self._shadow_engine.process_audit_record(record)
            except Exception:
                # Shadow mode MUST NEVER affect audit or execution
                pass

    # --------------------------------------------------
    # Read-only accessors
    # --------------------------------------------------

    def all_records(self) -> List[dict]:
        """
        Return all persisted audit envelopes.
        """
        return list(self._records)

    def last_envelope_hash(self) -> Optional[str]:
        return self._last_hash

    # --------------------------------------------------
    # Shadow access (read-only, optional)
    # --------------------------------------------------

    def get_shadow_ledger(self):
        """
        Return current shadow ledger if enabled.
        """
        if not self._shadow_engine:
            return None
        return self._shadow_engine.get_ledger()

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    @staticmethod
    def _hash(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


# --------------------------------------------------
# Singleton authority
# --------------------------------------------------

_AUDIT_STORE = AuditStore()


def get_audit_store() -> AuditStore:
    return _AUDIT_STORE

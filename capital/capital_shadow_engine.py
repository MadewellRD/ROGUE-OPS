#
# capital/capital_shadow_engine.py
#
# Capital Shadow Engine
# PHASE 36b — AUDIT-DRIVEN (READ-ONLY)
#
# Purpose:
# - Consume execution audit records
# - Update ShadowLedger deterministically
#
# Explicitly NOT responsible for:
# - Execution
# - Risk decisions
# - Position sizing
# - PnL calculation
# - Broker interaction
#

import datetime as dt
from typing import Optional

from execution.execution_audit import AuditRecord
from capital.shadow_ledger import ShadowLedger, ShadowLedgerEntry


# ==================================================
# Capital Shadow Engine
# ==================================================

class CapitalShadowEngine:
    """
    Read-only processor that derives capital shape
    from execution audit records.

    This engine:
    - Is deterministic
    - Is replay-safe
    - Is suppressible
    - MUST NEVER block execution or audit
    """

    def __init__(self):
        self._ledger: Optional[ShadowLedger] = None

    # ----------------------------
    # Session handling
    # ----------------------------

    def _ensure_session(self, timestamp_utc: str) -> None:
        ts = dt.datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        session_date = ts.date()

        if self._ledger is None:
            self._ledger = ShadowLedger(session_date_utc=session_date)
            return

        if session_date != self._ledger.session_date_utc:
            # New session → reset ledger
            self._ledger = ShadowLedger(session_date_utc=session_date)

    # ----------------------------
    # Consume audit record
    # ----------------------------

    def process_audit_record(self, record: AuditRecord) -> None:
        """
        Consume an AuditRecord.

        Only execution-related records are processed.
        BLOCKED or rejected executions are ignored.
        """

        if record.record_type not in (
            "BROKER_ENTRY",
            "BROKER_EXIT",
            "SIM_ENTRY",
            "SIM_EXIT",
        ):
            return

        payload = record.payload
        intent = payload.get("intent")
        result = payload.get("status") or payload.get("result", {}).get("status")

        if result != "SUBMITTED":
            return

        executed_utc = payload.get("executed_utc") or payload.get(
            "result", {}
        ).get("executed_utc")

        if not executed_utc:
            return

        self._ensure_session(executed_utc)

        option = intent.get("option") if intent else None
        if not option:
            return  # Shadow mode is options-only

        entry = ShadowLedgerEntry(
            record_hash=record.record_hash,
            symbol=intent["symbol"],
            action=intent["action"],
            quantity=intent["quantity"],
            sec_type=intent["sec_type"],
            option_right=option["right"],
            timestamp_utc=executed_utc,
        )

        self._ledger.append(entry)

    # ----------------------------
    # Reporting (Read-only)
    # ----------------------------

    def get_ledger(self) -> Optional[ShadowLedger]:
        return self._ledger

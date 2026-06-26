#
# governance/go_no_go_gate.py
#
# OPS Production Go / No-Go Enforcement
# PHASE 46 — CHECKLIST AS LAW
#

import os
from datetime import datetime, timezone, timedelta

from governance.audit_store import get_audit_store
from execution.execution_audit import create_audit_record
from governance.kill_switch import kill_active


# ==================================================
# CONFIG
# ==================================================

CHECKLIST_ATTESTED = os.getenv("OPS_GO_NO_GO_ATTESTED", "false").lower() == "true"
KILL_DRILL_UTC = os.getenv("OPS_LAST_KILL_DRILL_UTC")  # ISO8601 Z
MAX_KILL_DRILL_AGE_HOURS = 24


# ==================================================
# Go / No-Go Enforcement
# ==================================================

def assert_go_no_go_passed() -> None:
    """
    Hard gate: OPS cannot enter CAPITAL without explicit attestation.
    """

    if not CHECKLIST_ATTESTED:
        raise RuntimeError("GO_NO_GO_NOT_ATTESTED")

    if kill_active():
        raise RuntimeError("KILL_ACTIVE_AT_STARTUP")

    _audit("GO_NO_GO_VERIFIED")


def assert_kill_drill_recent() -> None:
    """
    Kill switch must have been tested recently.
    """

    if not KILL_DRILL_UTC:
        raise RuntimeError("NO_KILL_DRILL_RECORDED")

    ts = datetime.fromisoformat(KILL_DRILL_UTC.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    age = now - ts
    if age > timedelta(hours=MAX_KILL_DRILL_AGE_HOURS):
        raise RuntimeError("KILL_DRILL_STALE")

    _audit("KILL_DRILL_VERIFIED")


# ==================================================
# Audit
# ==================================================

def _audit(event: str) -> None:
    audit = get_audit_store()
    audit.append(
        create_audit_record(
            record_type="OPS_GOVERNANCE",
            payload={
                "event": event,
                "timestamp_utc": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            },
        )
    )

#
# failure_manager.py
#
# Failure Modes & Resilience Authority
# PHASE 18 — ATOMIC (NO SUBPHASES)
#
# Responsible for:
# - Classifying system failures
# - Enforcing deterministic fail-safe responses
# - Triggering OPS halt conditions
# - Producing auditable failure records
#
# Explicitly NOT responsible for:
# - Recovery logic
# - Retries
# - Strategy adaptation
# - Broker reconnection
#

from enum import Enum, auto
from typing import Optional

from ops_state import get_ops_state
from execution_audit import create_audit_record
from audit_store import get_audit_store


# ----------------------------
# Failure taxonomy
# ----------------------------

class FailureType(Enum):
    BROKER_DISCONNECT = auto()
    PARTIAL_FILL = auto()
    MARKET_DATA_GAP = auto()
    TIME_SKEW = auto()
    UNEXPECTED_EXCEPTION = auto()


# ----------------------------
# Failure Manager
# ----------------------------

class FailureManager:
    """
    Deterministic failure authority.

    All failures result in explicit,
    auditable system responses.
    """

    def __init__(self):
        self.ops = get_ops_state()
        self.audit = get_audit_store()

    # ----------------------------
    # Failure handling
    # ----------------------------

    def handle_failure(
        self,
        *,
        failure: FailureType,
        context: Optional[dict] = None,
    ) -> None:
        """
        Handle a classified system failure.

        All failures:
        - Emit audit record
        - Halt OPS
        """

        # ----------------------------
        # Emit forensic record
        # ----------------------------
        self.audit.append(
            create_audit_record(
                record_type="SYSTEM_FAILURE",
                payload={
                    "failure_type": failure.name,
                    "context": context or {},
                },
            )
        )

        # ----------------------------
        # Enforce halt
        # ----------------------------
        self.ops.halt(reason=failure.name)

        # ----------------------------
        # Fail closed
        # ----------------------------
        return

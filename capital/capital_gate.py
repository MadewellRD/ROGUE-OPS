#
# capital_gate.py
#
# Capital Readiness Gate (FINAL)
# PHASE 31 + PHASE 46 — CAPITAL PROMOTION ENFORCEMENT
#
# Single authoritative gate for CAPITAL execution.
#
# Guarantees:
# - Deterministic
# - Replay-safe
# - Promotion-bound
# - Checklist-enforced
# - Impossible to bypass
#

from typing import Tuple
import os

from execution.execution_envelope import ExecutionEnvelope
from governance.ops_state import get_ops_state
from governance.go_no_go_gate import (
    assert_go_no_go_passed,
    assert_kill_drill_recent,
)
from capital.promotion_registry import (
    load_active_promotion,
    validate_promotion_for_envelope,
)


# ==================================================
# Environment (declared, NOT authoritative)
# ==================================================

ENV_EXECUTION_MODE = os.getenv("EXECUTION_MODE", "SIM").upper()
CAPITAL_ARMED = os.getenv("CAPITAL_ARMED", "false").lower() == "true"


# ==================================================
# Capital Authorization Gate (FINAL)
# ==================================================

def evaluate_capital_gate(
    envelope: ExecutionEnvelope,
) -> Tuple[bool, str]:
    """
    Determine whether CAPITAL execution is permitted.

    This gate is:
    - Deterministic
    - Replay-safe
    - Promotion-bound
    - Checklist-enforced
    - Fail-closed
    """

    # --------------------------------------------------
    # Only applies to CAPITAL
    # --------------------------------------------------

    if envelope.execution_mode != "CAPITAL":
        return True, "NOT_CAPITAL_MODE"

    # --------------------------------------------------
    # OPS STATE AUTHORITY
    # --------------------------------------------------

    ops = get_ops_state()
    if ops.get() != "CLEAR":
        return False, f"OPS_STATE_BLOCK:{ops.get()}"

    # --------------------------------------------------
    # ENVIRONMENT CONSISTENCY
    # --------------------------------------------------

    if ENV_EXECUTION_MODE != "CAPITAL":
        return False, "ENV_EXECUTION_MODE_MISMATCH"

    if not CAPITAL_ARMED:
        return False, "CAPITAL_NOT_ARMED"

    # --------------------------------------------------
    # GO / NO-GO CHECKLIST (MANDATORY)
    # --------------------------------------------------

    try:
        assert_go_no_go_passed()
    except Exception as e:
        return False, f"GO_NO_GO_BLOCK:{str(e)}"

    # --------------------------------------------------
    # KILL SWITCH DRILL REQUIREMENT
    # --------------------------------------------------

    try:
        assert_kill_drill_recent()
    except Exception as e:
        return False, f"KILL_DRILL_BLOCK:{str(e)}"

    # --------------------------------------------------
    # PROMOTION ARTIFACT (MANDATORY)
    # --------------------------------------------------

    promotion = load_active_promotion()
    if not promotion:
        return False, "NO_ACTIVE_PROMOTION"

    try:
        validate_promotion_for_envelope(promotion, envelope)
    except Exception as e:
        return False, f"PROMOTION_INVALID:{str(e)}"

    return True, "CAPITAL_ALLOWED"

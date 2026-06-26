#
# indicator_authority.py
#
# Indicator Authority Boundary
# PHASE 28 — INDICATOR ASSERTION AUTHORITY (ATOMIC)
#
# Responsible for:
# - Formally separating REQUIRED vs ADVISORY indicators
# - Providing a deterministic, auditable assertion object
#
# Explicitly NOT responsible for:
# - Indicator calculation
# - Indicator interpretation
# - Signal logic
# - Confidence scoring
# - Market data fetching
#

from dataclasses import dataclass
from typing import Dict, Any
import hashlib
import json


# ==================================================
# Indicator Assertion
# ==================================================

@dataclass(frozen=True)
class IndicatorAssertion:
    """
    Canonical indicator authority object.

    REQUIRED indicators determine whether a signal
    is allowed to exist.

    ADVISORY indicators may influence confidence
    in later phases but NEVER signal existence.
    """

    required: Dict[str, Any]
    advisory: Dict[str, Any]
    assertion_hash: str
    required_passed: bool


# ==================================================
# Canonical Constructor
# ==================================================

def create_indicator_assertion(
    *,
    required: Dict[str, Any],
    advisory: Dict[str, Any] | None = None,
) -> IndicatorAssertion:
    """
    Create a deterministic IndicatorAssertion.

    Fail-closed.
    Replay-safe.
    Authority-bound.
    """

    advisory = advisory or {}

    required_passed = bool(required) and all(
        v is not None for v in required.values()
    )

    payload = {
        "required": required,
        "advisory": advisory,
        "required_passed": required_passed,
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assertion_hash = hashlib.sha256(encoded).hexdigest()

    return IndicatorAssertion(
        required=required,
        advisory=advisory,
        assertion_hash=assertion_hash,
        required_passed=required_passed,
    )

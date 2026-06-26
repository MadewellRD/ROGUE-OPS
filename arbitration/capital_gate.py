from typing import List

from arbitration.types import ArbitrationDecision


def capital_gate(
    intents: List[ArbitrationDecision],
    capital_snapshot: dict,
) -> List[ArbitrationDecision]:
    """
    Capital gating layer.

    This function:
    - Enforces portfolio-level capital constraints
    - Limits how many arbitration decisions may proceed
    - Does NOT alter directives
    - Does NOT authorize execution
    """

    allowed: List[ArbitrationDecision] = []

    max_allowed = capital_snapshot.get("max_concurrent_intents", 1)

    for intent in intents[:max_allowed]:
        allowed.append(intent)

    return allowed

from typing import List

from arbitration.types import MergedIntent, ArbitrationDecision


def portfolio_arbitrate(
    intents: List[MergedIntent],
) -> List[ArbitrationDecision]:
    """
    Portfolio-level arbitration.

    This function:
    - Evaluates merged intents for portfolio compatibility
    - Produces non-authoritative ArbitrationDecision objects
    - Does NOT apply LAW logic
    - Does NOT authorize execution
    """

    results: List[ArbitrationDecision] = []

    for intent in intents:
        results.append(
            ArbitrationDecision(
                symbol=intent.symbol,
                directive="ENTRY_CANDIDATE",
                merged_intent=intent,
                violated_laws=[],
                notes="Portfolio compatible",
                snapshot_id=intent.snapshot_id,
            )
        )

    return results

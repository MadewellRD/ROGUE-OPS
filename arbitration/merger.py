from typing import List
from arbitration.types import StrategyIntent, MergedIntent


def merge_intents(intents: List[StrategyIntent]) -> List[MergedIntent]:
    merged = {}

    for intent in intents:
        key = (
            intent.symbol,
            intent.structure,
            intent.direction,
            intent.horizon,
            intent.risk_class,
        )

        if key not in merged:
            merged[key] = MergedIntent(
                symbol=intent.symbol,
                structure=intent.structure,
                direction=intent.direction,
                horizon=intent.horizon,
                risk_class=intent.risk_class,
                contributing_strategies=[intent.strategy_id],
                snapshot_id=intent.snapshot_id,
            )
        else:
            merged[key].contributing_strategies.append(intent.strategy_id)

    return list(merged.values())

from typing import List, Dict
from arbitration.types import MergedIntent


def detect_soft_conflicts(
    intents: List[MergedIntent],
) -> Dict[int, List[int]]:
    conflicts: Dict[int, List[int]] = {}

    for i, a in enumerate(intents):
        for j, b in enumerate(intents):
            if i == j:
                continue

            if a.symbol == b.symbol and a.direction != b.direction:
                conflicts.setdefault(i, []).append(j)

    return conflicts

from abc import ABC, abstractmethod
from typing import List

from market.types.market_snapshot import MarketSnapshot
from arbitration.types import StrategyIntent


class StrategyModule(ABC):
    """
    Advisory-only strategy contract.

    Strategies:
    - Observe immutable MarketSnapshots
    - Propose zero or more StrategyIntents
    - NEVER authorize trades
    - NEVER allocate capital
    - NEVER interact with brokers
    """

    strategy_id: str

    @abstractmethod
    def evaluate(
        self,
        *,
        snapshot: MarketSnapshot,
        confidence_bias: int,
    ) -> List[StrategyIntent]:
        """
        Return zero or more StrategyIntent proposals.

        confidence_bias semantics:
            < 0  -> suppress / reduce
            = 0  -> neutral
            > 0  -> allow within strategy limits (never amplify)
        """
        raise NotImplementedError

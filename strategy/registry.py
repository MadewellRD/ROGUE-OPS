"""
Strategy Registry
SMC v1.0 — Authoritative Registry

Responsible for:
- Holding registered StrategyModules
- Enforcing uniqueness of strategy_id
- Providing deterministic iteration order
- Exposing a controlled discovery hook

Explicitly NOT responsible for:
- Strategy execution
- Evaluation timing
- Arbitration
- Dynamic imports (v1.0)
"""

from typing import Dict, List

from strategy.base import StrategyModule


class StrategyRegistry:
    """
    Canonical in-memory registry for StrategyModules.

    v1.0 characteristics:
    - Explicit registration only
    - Deterministic iteration
    - Discovery is a no-op placeholder
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, StrategyModule] = {}

    # --------------------------------------------------
    # Registration
    # --------------------------------------------------

    def register(self, strategy: StrategyModule) -> None:
        """
        Register a StrategyModule instance.

        Raises if strategy_id is duplicated.
        """
        strategy_id = strategy.strategy_id

        if not strategy_id:
            raise ValueError("StrategyModule.strategy_id must be set")

        if strategy_id in self._strategies:
            raise ValueError(f"Duplicate strategy_id: {strategy_id}")

        self._strategies[strategy_id] = strategy

    # --------------------------------------------------
    # Accessors
    # --------------------------------------------------

    def all(self) -> List[StrategyModule]:
        """
        Return all registered strategies in deterministic order.
        """
        return list(self._strategies.values())

    def get(self, strategy_id: str) -> StrategyModule:
        return self._strategies[strategy_id]

    # --------------------------------------------------
    # Discovery Hook (v1.0 NO-OP)
    # --------------------------------------------------

    def discover(self) -> None:
        """
        Placeholder for future strategy discovery.

        v1.0 behavior:
        - No filesystem scanning
        - No dynamic imports
        - Strategies must be registered explicitly
        """
        return

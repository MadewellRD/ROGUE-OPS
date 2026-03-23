#
# multi_symbol_orchestrator.py
#
# Multi-Symbol Orchestrator
# PHASE 35 — FAN-OUT ONLY (NON-AUTHORITATIVE)
#
# Purpose:
# - Sequentially execute the full OPS pipeline per symbol
# - Preserve single-symbol authority boundaries
# - Provide deterministic, kill-aware orchestration
#
# Explicitly NOT responsible for:
# - Strategy selection
# - Signal ranking
# - Capital allocation across symbols
# - Confidence comparison
# - Portfolio logic
#
# Each symbol is treated as an independent universe.
#

import os
from typing import List, Dict, Any

from kill_switch import kill_active
from paper_trade_driver import main as run_single_symbol_demo


# ==================================================
# Orchestrator
# ==================================================

class MultiSymbolOrchestrator:
    """
    Phase 35 fan-out orchestrator.

    This orchestrator:
    - Runs symbols sequentially (deterministic)
    - Aborts immediately on kill
    - Does not share state between symbols
    """

    def __init__(self, *, symbols: List[str]):
        if not symbols:
            raise RuntimeError("MultiSymbolOrchestrator requires at least one symbol")

        self.symbols = symbols

    def run(self) -> Dict[str, Any]:
        """
        Execute the OPS pipeline once per symbol.

        Returns:
            Dict keyed by symbol with execution status metadata.
        """

        results: Dict[str, Any] = {}

        for symbol in self.symbols:
            if kill_active():
                raise RuntimeError(
                    "Kill switch activated — multi-symbol orchestration aborted"
                )

            print("\n" + "=" * 60)
            print(f"[PHASE 35] START SYMBOL: {symbol}")
            print("=" * 60)

            # --------------------------------------------------
            # Environment isolation per symbol
            # --------------------------------------------------
            os.environ["OPS_ACTIVE_SYMBOL"] = symbol

            try:
                run_single_symbol_demo()
                results[symbol] = {"status": "COMPLETED"}
            except Exception as e:
                results[symbol] = {
                    "status": "FAILED",
                    "error": str(e),
                }

            print("\n" + "-" * 60)
            print(f"[PHASE 35] END SYMBOL: {symbol}")
            print("-" * 60)

        return results


# ==================================================
# CLI Entry Point (Optional)
# ==================================================

def main() -> None:
    """
    Optional manual entry point.

    Example:
        python3 multi_symbol_orchestrator.py
    """

    symbols = ["SPY", "IWM"]

    orchestrator = MultiSymbolOrchestrator(symbols=symbols)
    results = orchestrator.run()

    print("\n[PHASE 35 SUMMARY]")
    for sym, meta in results.items():
        print(f"  {sym}: {meta}")


if __name__ == "__main__":
    main()

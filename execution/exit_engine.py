#
# exit_engine.py
#
# Exit Engine — Deterministic, Indicator-Aware
# PHASE 21.2 — EXIT SIGNAL AUTHORITY (ATOMIC)
#
# Responsible for:
# - Determining when an open position must exit
# - Enforcing 0DTE hard stops
# - Applying indicator-based exit logic
# - Producing deterministic ExitDirective
#
# EXIT IS SUPREME:
# - EXIT may bypass risk
# - EXIT may bypass authorization
# - EXIT may NOT bypass OPS / Kill
#
# Explicitly NOT responsible for:
# - Order execution
# - Position mutation
# - Market data fetching
# - Indicator fetching
#

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any

from execution.position import Position
from market.market_data import MarketSnapshot


# ==================================================
# Exit directive
# ==================================================

@dataclass(frozen=True)
class ExitDirective:
    """
    Deterministic instruction to exit a position.
    """

    reason: Literal[
        "TIME_HARD_STOP",
        "KILL_SWITCH",
        "INDICATOR_REVERSAL",
    ]


# ==================================================
# Exit Engine
# ==================================================

class ExitEngine:
    """
    Deterministic exit authority.

    Consumes:
    - Position
    - MarketSnapshot
    - Indicator assertions (pre-fetched)

    Produces:
    - ExitDirective or None
    """

    # --------------------------------------------------
    # HARD TIME STOP (0DTE)
    # US market close = 21:00 UTC
    # --------------------------------------------------
    HARD_EXIT_TIME_UTC = dt.time(20, 55)  # 5-minute buffer

    # --------------------------------------------------
    # Indicator thresholds (AUTHORITATIVE)
    # --------------------------------------------------
    RSI_EXIT_OVERBOUGHT = 70.0
    RSI_EXIT_OVERSOLD = 30.0


    def evaluate(
        self,
        *,
        position: Position,
        snapshot: MarketSnapshot,
        indicators: Dict[str, Any],
        ops_halted: bool,
    ) -> Optional[ExitDirective]:
        """
        Determine whether the position must exit.

        Inputs:
            position     : Open Position (Phase C1)
            snapshot     : MarketSnapshot (Phase 10)
            indicators   : Aggregated indicator assertions
            ops_halted   : OPS or Kill state

        Returns:
            ExitDirective if exit required, else None
        """

        # --------------------------------------------------
        # Kill / OPS override (absolute)
        # --------------------------------------------------
        if ops_halted:
            return ExitDirective(reason="KILL_SWITCH")

        # --------------------------------------------------
        # Time-based hard stop (0DTE)
        # --------------------------------------------------
        now_utc = snapshot.timestamp_utc.time()

        if now_utc >= self.HARD_EXIT_TIME_UTC:
            return ExitDirective(reason="TIME_HARD_STOP")

        # --------------------------------------------------
        # Indicator-based exit (signal symmetry)
        # --------------------------------------------------
        rsi_value = indicators.get("RSI(7)")

        if isinstance(rsi_value, (int, float)):
            # Long CALL exit
            if position.right == "C" and rsi_value >= self.RSI_EXIT_OVERBOUGHT:
                return ExitDirective(reason="INDICATOR_REVERSAL")

            # Long PUT exit
            if position.right == "P" and rsi_value <= self.RSI_EXIT_OVERSOLD:
                return ExitDirective(reason="INDICATOR_REVERSAL")

        return None

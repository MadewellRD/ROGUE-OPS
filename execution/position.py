#
# execution/position.py
#
# Position Domain Model
# PHASE C5 — EXIT INTENT LINEAGE (FINAL)
#
# Immutable record of an open options position.
#

from dataclasses import dataclass
from typing import Literal
import datetime as dt

from execution.execution_contracts import ExecutionIntent, OptionSpec, now_utc


@dataclass(frozen=True)
class Position:
    """
    Immutable representation of a live position.
    """

    position_id: str

    # Instrument
    symbol: str
    sec_type: Literal["OPT"]
    expiry: str
    strike: float
    right: Literal["C", "P"]

    # Trade details
    action: Literal["BUY", "SELL"]
    quantity: int
    entry_price: float

    # Authority linkage
    intent_id: str
    envelope_hash: str

    # Time
    opened_at_utc: dt.datetime

    # ==================================================
    # Exit intent authority (CANONICAL)
    # ==================================================

    def to_exit_intent(self) -> ExecutionIntent:
        """
        Derive a deterministic EXIT ExecutionIntent
        that closes this position.

        This method:
        - Preserves lineage
        - Uses canonical helpers only
        - Is replay-safe and audit-complete
        """

        option = OptionSpec(
            expiry=self.expiry,
            strike=self.strike,
            right=self.right,
        )

        parent_intent = ExecutionIntent(
            intent_id=self.intent_id,
            parent_intent_id=None,
            created_utc=now_utc(),
            symbol=self.symbol,
            sec_type=self.sec_type,
            quantity=self.quantity,
            action=self.action,
            strategy_tag="ORIGINAL",
            option=option,
        )

        return parent_intent.derive_exit()

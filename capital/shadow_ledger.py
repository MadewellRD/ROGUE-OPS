#
# shadow_ledger.py
#
# Capital Shadow Ledger
# PHASE 36a — IMMUTABLE, APPEND-ONLY (NON-AUTHORITATIVE)
#
# Purpose:
# - Maintain a deterministic, replay-safe shadow ledger
# - Track capital *shape*, not capital truth
#
# Explicitly NOT responsible for:
# - Execution
# - Pricing
# - PnL estimation
# - Risk enforcement
# - Any feedback into OPS
#

from dataclasses import dataclass, field
from typing import Dict, List
import datetime as dt


# ==================================================
# Ledger Entry
# ==================================================

@dataclass(frozen=True)
class ShadowLedgerEntry:
    """
    Immutable shadow ledger entry derived from audit truth.
    """

    record_hash: str
    symbol: str
    action: str           # BUY / SELL
    quantity: int
    sec_type: str         # OPT
    option_right: str     # C / P
    timestamp_utc: str


# ==================================================
# Shadow Ledger (Session-Scoped)
# ==================================================

@dataclass
class ShadowLedger:
    """
    Append-only capital shadow ledger.

    This ledger:
    - Is session-scoped
    - Is replay-safe
    - Contains NO pricing assumptions
    """

    session_date_utc: dt.date
    entries: List[ShadowLedgerEntry] = field(default_factory=list)

    # ----------------------------
    # Append (ONLY operation)
    # ----------------------------

    def append(self, entry: ShadowLedgerEntry) -> None:
        self.entries.append(entry)

    # ----------------------------
    # Deterministic Metrics
    # ----------------------------

    def total_trades(self) -> int:
        return len(self.entries)

    def total_contracts(self) -> int:
        return sum(e.quantity for e in self.entries)

    def contracts_by_symbol(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.entries:
            out[e.symbol] = out.get(e.symbol, 0) + e.quantity
        return out

    def directional_exposure(self) -> Dict[str, int]:
        """
        CALL vs PUT exposure (contract count).
        """
        exposure = {"CALL": 0, "PUT": 0}
        for e in self.entries:
            if e.option_right == "C":
                exposure["CALL"] += e.quantity
            elif e.option_right == "P":
                exposure["PUT"] += e.quantity
        return exposure

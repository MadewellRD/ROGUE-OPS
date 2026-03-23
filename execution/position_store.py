#
# execution/position_store.py
#
# Position State Authority
# PHASE 12 — ATOMIC (NO SUBPHASES)
#
# Responsible for:
# - Holding the single open position
# - Enforcing one-position-only invariant
#
# Explicitly NOT responsible for:
# - Exit decisions
# - PnL management
# - Broker interaction
#

from typing import Optional
from execution.position import Position


class PositionStore:
    """
    In-memory authoritative position store.

    Exactly one open position is permitted.
    """

    def __init__(self):
        self._open_position: Optional[Position] = None

    # ----------------------------
    # Queries
    # ----------------------------

    def has_open_position(self) -> bool:
        return self._open_position is not None

    def get_open_position(self) -> Position:
        if self._open_position is None:
            raise RuntimeError("No open position exists")
        return self._open_position

    # ----------------------------
    # Mutations (authoritative)
    # ----------------------------

    def open_position(self, position: Position) -> None:
        if self._open_position is not None:
            raise RuntimeError("Position already open")
        self._open_position = position

    def close_position(self) -> Position:
        if self._open_position is None:
            raise RuntimeError("No position to close")

        closed = self._open_position
        self._open_position = None
        return closed


# ----------------------------
# Singleton authority
# ----------------------------

_POSITION_STORE = PositionStore()


def get_position_store() -> PositionStore:
    return _POSITION_STORE

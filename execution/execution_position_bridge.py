#
# execution/execution_position_bridge.py
#
# Execution → Position Bridge
# PHASE 15 + PHASE 59 — ATOMIC WITH REALIZED P&L
#
# Responsible for:
# - Translating ExecutionResult into authoritative Position mutations
# - Computing realized P&L at EXIT
# - Advancing StateMachine lifecycle callbacks
#
# Explicitly NOT responsible for:
# - Execution routing
# - Risk decisions
# - Strategy logic
# - Market data
# - Persistence beyond position store
#

import datetime as dt
import uuid

from execution.execution_envelope import ExecutionEnvelope
from execution.execution_contracts import ExecutionResult
from execution.position import Position
from execution.position_store import get_position_store
from execution.state_machine import StateMachineV2


class ExecutionPositionBridge:
    """
    Authoritative bridge between execution results
    and position state.

    This replaces all test harness mutation logic.
    """

    def __init__(self, *, state_machine: StateMachineV2):
        self.state_machine = state_machine
        self.positions = get_position_store()

    # ==================================================
    # ENTRY HANDLING
    # ==================================================

    def handle_entry(
        self,
        *,
        envelope: ExecutionEnvelope,
        result: ExecutionResult,
        entry_price: float,
    ) -> None:
        """
        Handle successful position entry.
        """

        if result.status != "SUBMITTED":
            raise RuntimeError("Cannot open position — execution not submitted")

        intent = envelope.intent

        if intent.sec_type != "OPT":
            raise RuntimeError("Phase 15 only supports options positions")

        position = Position(
            position_id=str(uuid.uuid4()),
            symbol=intent.symbol,
            sec_type="OPT",
            expiry=intent.option.expiry,
            strike=intent.option.strike,
            right=intent.option.right,
            action=intent.action,
            quantity=intent.quantity,
            entry_price=entry_price,
            intent_id=intent.intent_id,
            envelope_hash=envelope.envelope_hash,
            opened_at_utc=dt.datetime.utcnow(),
        )

        # Authoritative mutation
        self.positions.open_position(position)

        # Advance lifecycle
        self.state_machine.on_position_opened()

    # ==================================================
    # EXIT HANDLING (PHASE 59)
    # ==================================================

    def handle_exit(
        self,
        *,
        envelope: ExecutionEnvelope,
        result: ExecutionResult,
    ) -> dict:
        """
        Handle successful position exit.

        RETURNS:
        {
            "realized_pnl_usd": float
        }
        """

        if result.status != "SUBMITTED":
            raise RuntimeError("Cannot close position — execution not submitted")

        if not self.positions.has_open_position():
            raise RuntimeError("No open position to close")

        # --------------------------------------------------
        # Retrieve position BEFORE mutation
        # --------------------------------------------------

        position = self.positions.get_open_position()

        # --------------------------------------------------
        # Exit price (authoritative execution result)
        # --------------------------------------------------

        exit_price = result.raw.get("fill_price")
        if exit_price is None:
            raise RuntimeError("EXIT_FILL_PRICE_MISSING")

        # --------------------------------------------------
        # Realized P&L computation (brokerage-grade)
        # --------------------------------------------------

        multiplier = 100  # Options contract multiplier
        qty = position.quantity

        if position.action == "BUY":
            pnl = (exit_price - position.entry_price) * qty * multiplier
        else:
            pnl = (position.entry_price - exit_price) * qty * multiplier

        realized_pnl = round(pnl, 2)

        # --------------------------------------------------
        # Paired-trade record (entry + exit) for the scorecard.
        # Captured BEFORE we drop the position; advisory only.
        # --------------------------------------------------

        opened = getattr(position, "opened_at_utc", None)
        closed = dt.datetime.utcnow()
        held_seconds = (closed - opened).total_seconds() if isinstance(opened, dt.datetime) else None

        paired = {
            "realized_pnl_usd": realized_pnl,
            "symbol": position.symbol,
            "right": position.right,
            "strike": position.strike,
            "expiry": position.expiry,
            "action": position.action,            # entry side (BUY/SELL)
            "quantity": qty,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "opened_at_utc": str(opened) if opened else None,
            "closed_at_utc": closed.replace(microsecond=0).isoformat() + "Z",
            "held_seconds": round(held_seconds, 1) if held_seconds is not None else None,
            "envelope_hash": getattr(envelope, "envelope_hash", None),
            "execution_mode": getattr(envelope, "execution_mode", None),
        }

        # --------------------------------------------------
        # Authoritative mutation
        # --------------------------------------------------

        self.positions.close_position()

        # Advance lifecycle
        self.state_machine.on_position_closed()
        self.state_machine.on_audit_complete()

        return paired

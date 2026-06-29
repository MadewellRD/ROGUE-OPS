#
# execution/position_sizing_authority.py
#
# Position Sizing Authority — Capital Expression Layer
# PHASE 34a + PHASE 47 — BALANCE-AWARE SIZING (NON-PERMISSIVE)
#

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from execution.execution_envelope import ExecutionEnvelope
from governance.kill_switch import kill_active, kill_context
from capital.account_balance_authority import (
    AccountBalanceAuthority,
    AccountBalanceSnapshot,
)


# ==================================================
# Sized Execution Envelope (DERIVED)
# ==================================================

@dataclass(frozen=True)
class SizedExecutionEnvelope:
    """
    Derived, immutable execution envelope with final executable quantity.
    """

    base_envelope: ExecutionEnvelope
    final_quantity: int
    sizing_reason: Dict[str, Any]


# ==================================================
# Position Sizing Authority
# ==================================================

class PositionSizingAuthority:
    """
    Deterministic, fail-closed, balance-aware sizing authority.
    """

    ENGINE_VERSION = "PHASE34_47_POSITION_SIZING_V3"

    @staticmethod
    def size(
        *,
        envelope: ExecutionEnvelope,
        account_id: str,
        max_contracts: int,
        max_notional_usd: Optional[float] = None,
        max_pct_of_net_liq: float = 0.02,
        max_pct_of_available: float = 0.25,
    ) -> SizedExecutionEnvelope:
        """
        Produce a SizedExecutionEnvelope.

        Balance awareness may ONLY reduce size.
        """

        # --------------------------------------------------
        # Kill dominance
        # --------------------------------------------------

        if kill_active():
            ctx = kill_context()
            raise RuntimeError(
                f"KILL ACTIVE — sizing blocked "
                f"(reason={ctx.get('reason')}, ts={ctx.get('timestamp_utc')})"
            )

        if envelope.action != "ENTRY":
            raise RuntimeError("Position sizing only applies to ENTRY")

        original_qty = envelope.intent.quantity
        if original_qty <= 0:
            raise RuntimeError("Invalid original quantity")

        # --------------------------------------------------
        # Balance snapshot (read-only)
        # --------------------------------------------------

        # SIM fabricates a deterministic balance (producer path). PAPER/CAPITAL
        # read the latest broker balance from the store, populated by the IBKR
        # runtime's streaming account-summary feed (under ROGUE_BALANCE_ACCOUNT,
        # default "IBKR"). The producer FORBIDS broker IO inside this authority.
        if envelope.execution_mode == "SIM":
            balance: AccountBalanceSnapshot = AccountBalanceAuthority.snapshot(
                account_id=account_id,
                execution_mode="SIM",
            )
        else:
            balance = AccountBalanceAuthority.get_cached_snapshot(
                account_id=os.getenv("ROGUE_BALANCE_ACCOUNT", "IBKR"),
                max_age_seconds=int(os.getenv("BALANCE_MAX_AGE_SEC", "300")),
            )

        sizing_reason: Dict[str, Any] = {
            "engine_version": PositionSizingAuthority.ENGINE_VERSION,
            "original_quantity": original_qty,
            "balance_snapshot_hash": balance.snapshot_hash,
            "net_liquidation": balance.net_liquidation,
            "available_funds": balance.available_funds,
        }

        # --------------------------------------------------
        # Contract ceiling
        # --------------------------------------------------

        final_qty = min(original_qty, max_contracts)
        sizing_reason["contract_ceiling"] = max_contracts

        # --------------------------------------------------
        # Notional ceiling
        # --------------------------------------------------

        opt = envelope.intent.option
        if not opt:
            raise RuntimeError("Notional sizing requires option context")

        per_contract_notional = opt.strike * opt.multiplier

        if max_notional_usd is not None:
            max_qty_by_notional = int(max_notional_usd // per_contract_notional)
            final_qty = min(final_qty, max_qty_by_notional)
            sizing_reason["max_qty_by_notional"] = max_qty_by_notional

        # --------------------------------------------------
        # Balance-relative ceilings (PRODUCTION ONLY)
        # --------------------------------------------------

        if envelope.execution_mode != "SIM":
            max_notional_by_netliq = balance.net_liquidation * max_pct_of_net_liq
            max_notional_by_available = (
                balance.available_funds * max_pct_of_available
            )

            effective_notional_cap = min(
                max_notional_by_netliq,
                max_notional_by_available,
            )

            max_qty_by_balance = int(
                effective_notional_cap // per_contract_notional
            )

            final_qty = min(final_qty, max_qty_by_balance)

            sizing_reason.update(
                {
                    "max_pct_net_liq": max_pct_of_net_liq,
                    "max_pct_available": max_pct_of_available,
                    "effective_notional_cap": effective_notional_cap,
                    "max_qty_by_balance": max_qty_by_balance,
                }
            )
        else:
            sizing_reason["balance_caps_skipped"] = True

        # --------------------------------------------------
        # Fail closed
        # --------------------------------------------------

        if final_qty <= 0:
            raise RuntimeError(
                "Sizing reduced quantity to zero — trade blocked"
            )

        sizing_reason["final_quantity"] = final_qty

        return SizedExecutionEnvelope(
            base_envelope=envelope,
            final_quantity=final_qty,
            sizing_reason=sizing_reason,
        )

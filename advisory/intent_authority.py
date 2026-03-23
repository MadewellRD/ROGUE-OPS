#
# intent_authority.py
#
# Intent Authority
# PHASE 26 — TIME-AWARE ENTRY AUTHORIZATION (FINAL)
#
# Responsible for:
# - Deciding WHETHER to emit an ExecutionIntent
# - Enforcing ENTRY eligibility via Time Authority
#
# Explicitly NOT responsible for:
# - Time definition
# - Market session calendars
# - Option discovery
# - Risk sizing
# - Execution
# - Position mutation
#

from execution_contracts import ExecutionIntent
from market_data import MarketSnapshot
from position_store import get_position_store
from time_authority import evaluate_entry_time


class IntentAuthority:
    """
    Deterministic intent authority.

    ENTRY authorization is binary and fail-closed.
    All time eligibility is delegated to time_authority.
    """

    SYMBOL = "SPY"
    ACTION = "BUY"
    RIGHT = "C"
    QTY = 1

    def evaluate(self, snapshot: MarketSnapshot):
        """
        Evaluate whether an ExecutionIntent should be emitted.

        Returns:
            ExecutionIntent or None
        """

        # ----------------------------
        # Position invariant
        # ----------------------------
        store = get_position_store()
        if store.has_open_position():
            return None

        # ----------------------------
        # Symbol gate
        # ----------------------------
        if snapshot.symbol != self.SYMBOL:
            return None

        # ----------------------------
        # Session gate
        # ----------------------------
        if snapshot.session != "REGULAR":
            return None

        # ----------------------------
        # ENTRY time authority (PHASE 26)
        # ----------------------------
        allowed, reason = evaluate_entry_time(snapshot.timestamp_utc)
        if not allowed:
            return None

        # ----------------------------
        # Deterministic ATM strike
        # ----------------------------
        strike = round(snapshot.spot)
        expiry = snapshot.timestamp_utc.strftime("%Y%m%d")

        # ----------------------------
        # Emit canonical intent
        # ----------------------------
        return ExecutionIntent.option(
            symbol=self.SYMBOL,
            qty=self.QTY,
            action=self.ACTION,
            expiry=expiry,
            strike=strike,
            right=self.RIGHT,
            tag="PHASE_26_TIME_AUTHORIZED_ENTRY",
        )

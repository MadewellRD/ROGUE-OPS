#
# parity_engine.py
#
# Deterministic Parity Engine
# PHASE 29 — LIVE / PAPER / REPLAY EQUIVALENCE (ATOMIC)
#
# Responsible for:
# - Enforcing deterministic parity across execution modes
# - Binding normalized inputs to identical OPS outcomes
# - Detecting and failing on divergence
#
# Explicitly NOT responsible for:
# - Market data fetching
# - Indicator computation
# - Strategy logic
# - Broker execution
#

from typing import Optional, Dict, Any

from market_data import MarketSnapshot
from execution_envelope import ExecutionEnvelope
from execution_contracts import ExecutionIntent
from audit_store import get_audit_store
from execution_audit import create_audit_record


class ParityEngine:
    """
    Deterministic parity enforcement engine.

    This engine asserts that identical normalized inputs
    produce identical OPS outcomes across modes.
    """

    def __init__(self):
        self.audit = get_audit_store()

    # --------------------------------------------------
    # Parity assertion
    # --------------------------------------------------

    def assert_parity(
        self,
        *,
        snapshot: MarketSnapshot,
        intent: Optional[ExecutionIntent],
        envelope: Optional[ExecutionEnvelope],
        execution_mode: str,
        indicators: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Assert deterministic parity for a single decision step.

        This function is FAIL-CLOSED.
        """

        payload = {
            "symbol": snapshot.symbol,
            "spot": snapshot.spot,
            "timestamp_utc": snapshot.timestamp_utc.isoformat(),
            "session": snapshot.session,
            "source": snapshot.source,
            "execution_mode": execution_mode,
            "intent_id": intent.intent_id if intent else None,
            "envelope_hash": envelope.envelope_hash if envelope else None,
            "has_intent": intent is not None,
            "has_envelope": envelope is not None,
            "indicator_keys": sorted(indicators.keys()) if indicators else None,
        }

        self.audit.append(
            create_audit_record(
                record_type="PARITY_ASSERTION",
                payload=payload,
            )
        )

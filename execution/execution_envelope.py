#
# execution/execution_envelope.py
#
# Sealed Execution Envelope
# OPS / Brokerage-grade
# STEP 2 — EXECUTION ENVELOPE AUTHORITY (FINAL)
# PHASE C2 + PHASE 27 + PHASE 45 — SEALED, VERSIONED, FAIL-CLOSED
#

from dataclasses import dataclass
import hashlib
import json
import datetime as dt
from typing import Dict, Any, Literal

from execution.execution_contracts import ExecutionIntent
from governance.kill_switch import kill_active, kill_context


# ==================================================
# Canonical envelope metadata
# ==================================================

SCHEMA_VERSION = "EXECUTION_ENVELOPE_V1"
ENGINE_VERSION = "ROGUE_OPS_CORE_V1"

# LAW version hash must be updated ONLY when Tier-1 LAW changes
LAW_VERSION_HASH = "LAW_V1_HASH_PLACEHOLDER"


# ==================================================
# Canonical envelope types
# ==================================================

OPSState = Literal["CLEAR", "CAUTION", "HALT"]

ExecutionAction = Literal["ENTRY", "EXIT"]

ExecutionMode = Literal["SIM", "PAPER", "CAPITAL"]


# ==================================================
# Execution Envelope (SEALED)
# ==================================================

@dataclass(frozen=True)
class ExecutionEnvelope:
    """
    Sealed, immutable execution envelope.

    This object is a COURT ORDER.
    It is the ONLY object permitted to reach execution.

    Properties:
    - Immutable
    - Versioned
    - Cryptographically sealed
    - Replay-safe
    - Kill-dominant
    """

    # Core intent
    intent: ExecutionIntent

    # Execution classification
    action: ExecutionAction
    execution_mode: ExecutionMode

    # Governance snapshot
    ops_state: OPSState

    # Authorization flags
    risk_ok: bool
    authorized: bool

    # Metadata
    schema_version: str
    engine_version: str
    law_version_hash: str

    # Audit fields
    created_utc: str
    envelope_hash: str
    seal_hash: str


    # ==================================================
    # Canonical constructor (SEALED)
    # ==================================================

    @staticmethod
    def create(
        *,
        intent: ExecutionIntent,
        action: ExecutionAction,
        execution_mode: ExecutionMode,
        ops_state: OPSState,
        risk_ok: bool,
        authorized: bool,
    ) -> "ExecutionEnvelope":
        """
        Create a sealed, immutable execution envelope.

        FAIL-CLOSED.
        Kill-dominant.
        Illegal states are structurally impossible.
        """

        # --------------------------------------------------
        # GLOBAL KILL AUTHORITY (ABSOLUTE)
        # --------------------------------------------------

        if kill_active():
            ctx = kill_context()
            raise RuntimeError(
                f"KILL ACTIVE — envelope creation blocked "
                f"(reason={ctx.get('reason')}, ts={ctx.get('timestamp_utc')})"
            )

        # --------------------------------------------------
        # OPS HALT
        # --------------------------------------------------

        if ops_state == "HALT":
            raise RuntimeError("OPS HALT — envelope creation blocked")

        # --------------------------------------------------
        # Execution action validation
        # --------------------------------------------------

        if action not in ("ENTRY", "EXIT"):
            raise RuntimeError(f"Invalid execution action: {action}")

        if execution_mode not in ("SIM", "PAPER", "CAPITAL"):
            raise RuntimeError(f"Invalid execution mode: {execution_mode}")

        # --------------------------------------------------
        # ENTRY authority rules
        # --------------------------------------------------

        if action == "ENTRY":
            if not authorized:
                raise RuntimeError("ENTRY not authorized")

            if not risk_ok:
                raise RuntimeError("ENTRY blocked by risk veto")

        # --------------------------------------------------
        # Timestamp (deterministic, UTC)
        # --------------------------------------------------

        created_utc = ExecutionEnvelope._now_utc()

        # --------------------------------------------------
        # Envelope content hash (WHAT happened)
        # --------------------------------------------------

        envelope_payload = {
            "intent": ExecutionEnvelope._intent_payload(intent),
            "signal_context_hash": intent.signal_context_hash,
            "action": action,
            "execution_mode": execution_mode,
            "ops_state": ops_state,
            "risk_ok": risk_ok,
            "authorized": authorized,
            "created_utc": created_utc,
        }

        envelope_hash = ExecutionEnvelope._hash(envelope_payload)

        # --------------------------------------------------
        # Authority seal hash (WHY it was allowed)
        # --------------------------------------------------

        seal_payload = {
            "envelope_hash": envelope_hash,
            "schema_version": SCHEMA_VERSION,
            "engine_version": ENGINE_VERSION,
            "law_version_hash": LAW_VERSION_HASH,
        }

        seal_hash = ExecutionEnvelope._hash(seal_payload)

        return ExecutionEnvelope(
            intent=intent,
            action=action,
            execution_mode=execution_mode,
            ops_state=ops_state,
            risk_ok=risk_ok,
            authorized=authorized,
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            law_version_hash=LAW_VERSION_HASH,
            created_utc=created_utc,
            envelope_hash=envelope_hash,
            seal_hash=seal_hash,
        )


    # ==================================================
    # Seal verification (MANDATORY)
    # ==================================================

    def verify_seal(self) -> None:
        """
        Verify envelope integrity and authority seal.

        MUST be called before execution.
        """

        recomputed_envelope_hash = self._hash(
            {
                "intent": self._intent_payload(self.intent),
                "signal_context_hash": self.intent.signal_context_hash,
                "action": self.action,
                "execution_mode": self.execution_mode,
                "ops_state": self.ops_state,
                "risk_ok": self.risk_ok,
                "authorized": self.authorized,
                "created_utc": self.created_utc,
            }
        )

        if recomputed_envelope_hash != self.envelope_hash:
            raise RuntimeError("Envelope content hash mismatch — execution blocked")

        recomputed_seal_hash = self._hash(
            {
                "envelope_hash": self.envelope_hash,
                "schema_version": self.schema_version,
                "engine_version": self.engine_version,
                "law_version_hash": self.law_version_hash,
            }
        )

        if recomputed_seal_hash != self.seal_hash:
            raise RuntimeError("Envelope seal hash mismatch — execution blocked")


    # ==================================================
    # Deterministic helpers
    # ==================================================

    @staticmethod
    def _now_utc() -> str:
        return (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _intent_payload(intent: ExecutionIntent) -> Dict[str, Any]:
        data = {
            "intent_id": intent.intent_id,
            "parent_intent_id": intent.parent_intent_id,
            "created_utc": intent.created_utc,
            "symbol": intent.symbol,
            "sec_type": intent.sec_type,
            "quantity": intent.quantity,
            "action": intent.action,
            "strategy_tag": intent.strategy_tag,
            "signal_context_hash": intent.signal_context_hash,
        }

        if intent.option:
            data["option"] = {
                "expiry": intent.option.expiry,
                "strike": intent.option.strike,
                "right": intent.option.right,
                "multiplier": intent.option.multiplier,
            }

        return data

    @staticmethod
    def _hash(payload: Dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


    # ==================================================
    # Audit / replay
    # ==================================================

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "engine_version": self.engine_version,
            "law_version_hash": self.law_version_hash,
            "envelope_hash": self.envelope_hash,
            "seal_hash": self.seal_hash,
            "created_utc": self.created_utc,
            "action": self.action,
            "execution_mode": self.execution_mode,
            "ops_state": self.ops_state,
            "risk_ok": self.risk_ok,
            "authorized": self.authorized,
            "signal_context_hash": self.intent.signal_context_hash,
            "intent": self._intent_payload(self.intent),
        }

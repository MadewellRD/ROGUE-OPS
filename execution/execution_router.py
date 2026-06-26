#
# execution/execution_router.py
#
# OPS-compliant execution router (SEALED)
# PHASE C5 + PHASE 27 + PHASE 31 + PHASE 34b + PHASE 45 + PHASE 47
#
# Envelope-only (EXIT), Sized-envelope (ENTRY),
# mode-aware, exit-supreme,
# capital-authorized, audit-complete,
# SEAL-VERIFIED (NON-BYPASSABLE),
# BALANCE-AWARE SIZING
#

import hashlib
import json

from execution.execution_envelope import ExecutionEnvelope
from execution.position_sizing_authority import (
    SizedExecutionEnvelope,
    PositionSizingAuthority,
)
from execution.execution_contracts import ExecutionResult, now_utc
from execution.execution_audit import create_audit_record
from governance.audit_store import get_audit_store
from governance.kill_switch import kill_active


# ==================================================
# EXECUTION LIMITS (MODE-AWARE, HARD BACKSTOPS)
# ==================================================

OPTION_MULTIPLIER = 100

# SIM — relaxed for deterministic testing ONLY
SIM_MAX_NOTIONAL_USD = 100_000
SIM_MAX_CONTRACTS = 10

# PAPER / CAPITAL — production hard limits
# Aligned to CAPITAL_GO_LIVE_AUTHORIZATION.md (max 5 contracts / trade).
MAX_CAPITAL_NOTIONAL_USD = 5_000
MAX_CAPITAL_CONTRACTS = 5


# ==================================================
# PARITY ASSERTION HARNESS (EXTENDED)
# ==================================================

def _parity_fingerprint(envelope: ExecutionEnvelope, quantity: int) -> str:
    payload = {
        "envelope_hash": envelope.envelope_hash,
        "seal_hash": envelope.seal_hash,
        "signal_context_hash": envelope.intent.signal_context_hash,
        "symbol": envelope.intent.symbol,
        "sec_type": envelope.intent.sec_type,
        "quantity": quantity,
        "intent_action": envelope.intent.action,
        "execution_action": envelope.action,
        "execution_mode": envelope.execution_mode,
        "option": (
            {
                "expiry": envelope.intent.option.expiry,
                "strike": envelope.intent.option.strike,
                "right": envelope.intent.option.right,
                "multiplier": envelope.intent.option.multiplier,
            }
            if envelope.intent.option
            else None
        ),
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


# ==================================================
# SIM EXECUTION ORACLE (PURE)
# ==================================================

def _sim_execute(envelope: ExecutionEnvelope, quantity: int) -> ExecutionResult:
    parity = _parity_fingerprint(envelope, quantity)

    synthetic_order_id = int(
        hashlib.sha256(envelope.envelope_hash.encode()).hexdigest()[:8],
        16,
    )

    # Deterministic synthetic fill so the SIM lifecycle (open/close + P&L) is
    # exercisable end to end. Not a market model — SIM is a dry run.
    opt = envelope.intent.option
    fill_price = round(max(0.05, opt.strike * 0.002), 2) if opt else 1.00

    return ExecutionResult(
        status="SUBMITTED",
        order_id=synthetic_order_id,
        reason="SIM",
        executed_utc=now_utc(),
        parity_hash=parity,
        raw={"fill_price": fill_price, "sim": True},
    )


# ==================================================
# AUTHORITATIVE EXECUTION — EXIT
# ==================================================

def execute(envelope: ExecutionEnvelope, account_id: str) -> ExecutionResult:
    audit = get_audit_store()

    try:
        envelope.verify_seal()
    except Exception as e:
        return _blocked(audit, envelope, "ENVELOPE_SEAL_INVALID", {"error": str(e)})

    if envelope.action != "EXIT":
        return _blocked(audit, envelope, "UNSIZED_ENTRY_FORBIDDEN")

    if kill_active():
        return _blocked(audit, envelope, "KILL_SWITCH")

    if envelope.execution_mode == "SIM":
        result = _sim_execute(envelope, envelope.intent.quantity)
        _audit_exec(audit, "SIM_EXIT", envelope, result)
        return result

    from capital.capital_gate import evaluate_capital_gate
    from broker.broker_runtime import get_broker_runtime, BrokerCapabilityError

    allowed, reason = evaluate_capital_gate(envelope)
    if not allowed:
        return _blocked(audit, envelope, reason)

    try:
        runtime = get_broker_runtime(envelope.intent)
    except BrokerCapabilityError as e:
        return _blocked(audit, envelope, "BROKER_UNSUPPORTED", {"error": str(e)})

    try:
        broker_result = runtime.execute_intent(envelope.intent)
    except Exception as e:
        return _blocked(audit, envelope, "BROKER_EXCEPTION", {"error": str(e)})

    result = ExecutionResult(
        status="SUBMITTED",
        order_id=broker_result.order_id,
        reason=None,
        executed_utc=now_utc(),
        parity_hash=_parity_fingerprint(envelope, envelope.intent.quantity),
        raw=getattr(broker_result, "raw", {}),
    )

    _audit_exec(audit, "BROKER_EXIT", envelope, result)
    return result


# ==================================================
# AUTHORITATIVE EXECUTION — ENTRY (SIZED ONLY)
# ==================================================

def execute_sized(envelope: ExecutionEnvelope, account_id: str) -> ExecutionResult:
    audit = get_audit_store()

    try:
        envelope.verify_seal()
    except Exception as e:
        return _blocked(audit, envelope, "ENVELOPE_SEAL_INVALID", {"error": str(e)})

    if envelope.action != "ENTRY":
        return _blocked(audit, envelope, "SIZED_NON_ENTRY")

    if kill_active():
        return _blocked(audit, envelope, "KILL_SWITCH")

    # --------------------------------------------------
    # MODE-AWARE SIZING LIMITS
    # --------------------------------------------------

    if envelope.execution_mode == "SIM":
        max_contracts = SIM_MAX_CONTRACTS
        max_notional = SIM_MAX_NOTIONAL_USD
    else:
        max_contracts = MAX_CAPITAL_CONTRACTS
        max_notional = MAX_CAPITAL_NOTIONAL_USD

    # --------------------------------------------------
    # SIM PATH — PURE, BROKER-ISOLATED
    # --------------------------------------------------

    if envelope.execution_mode == "SIM":
        sized = PositionSizingAuthority.size(
            envelope=envelope,
            account_id=account_id,
            max_contracts=max_contracts,
            max_notional_usd=max_notional,
        )

        result = _sim_execute(envelope, sized.final_quantity)
        _audit_exec(audit, "SIM_ENTRY", envelope, result)
        return result

    # --------------------------------------------------
    # PAPER / CAPITAL PATH
    # --------------------------------------------------

    from capital.capital_gate import evaluate_capital_gate
    from broker.broker_runtime import get_broker_runtime, BrokerCapabilityError

    allowed, reason = evaluate_capital_gate(envelope)
    if not allowed:
        return _blocked(audit, envelope, reason)

    if not envelope.authorized or not envelope.risk_ok:
        return _blocked(audit, envelope, "RISK_OR_AUTH")

    sized: SizedExecutionEnvelope = PositionSizingAuthority.size(
        envelope=envelope,
        account_id=account_id,
        max_contracts=max_contracts,
        max_notional_usd=max_notional,
    )

    qty = sized.final_quantity
    strike = envelope.intent.option.strike
    notional = strike * OPTION_MULTIPLIER * qty

    if notional > MAX_CAPITAL_NOTIONAL_USD:
        return _blocked(audit, envelope, "CAPITAL_NOTIONAL_LIMIT", {"notional": notional})

    try:
        runtime = get_broker_runtime(envelope.intent)
    except BrokerCapabilityError as e:
        return _blocked(audit, envelope, "BROKER_UNSUPPORTED", {"error": str(e)})

    try:
        broker_result = runtime.execute_intent(
            envelope.intent,
            override_quantity=qty,
        )
    except Exception as e:
        return _blocked(audit, envelope, "BROKER_EXCEPTION", {"error": str(e)})

    result = ExecutionResult(
        status="SUBMITTED",
        order_id=broker_result.order_id,
        reason=None,
        executed_utc=now_utc(),
        parity_hash=_parity_fingerprint(envelope, qty),
        raw=getattr(broker_result, "raw", {}),
    )

    _audit_exec(audit, "BROKER_ENTRY", envelope, result)
    return result


# ==================================================
# AUDIT HELPERS
# ==================================================

def _blocked(audit, envelope, reason, extra=None) -> ExecutionResult:
    payload = {
        "reason": reason,
        "envelope_hash": envelope.envelope_hash,
        "seal_hash": envelope.seal_hash,
        "signal_context_hash": envelope.intent.signal_context_hash,
        "envelope": envelope.to_dict(),
    }
    if extra:
        payload.update(extra)

    audit.append(
        create_audit_record(
            record_type="EXECUTION_BLOCKED",
            payload=payload,
        )
    )

    return ExecutionResult(
        status="BLOCKED",
        order_id=None,
        reason=reason,
        executed_utc=now_utc(),
        parity_hash=None,
        raw={},
    )


def _audit_exec(audit, record_type, envelope, result: ExecutionResult) -> None:
    audit.append(
        create_audit_record(
            record_type=record_type,
            payload={
                "envelope_hash": envelope.envelope_hash,
                "seal_hash": envelope.seal_hash,
                "signal_context_hash": envelope.intent.signal_context_hash,
                "status": result.status,
                "order_id": result.order_id,
                "executed_utc": result.executed_utc,
                "parity_hash": result.parity_hash,
            },
        )
    )


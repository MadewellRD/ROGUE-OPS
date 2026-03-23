#
# execution_contracts.py
#
# Canonical Trade Intent + Result
# OPS / Brokerage-grade
# PHASE C5 + PHASE 27 — INTENT, RESULT & JUSTIFICATION AUTHORITY
#

from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any
import uuid
import datetime as dt


# ==================================================
# Type constraints
# ==================================================

SecurityType = Literal["STK", "OPT"]
ActionType = Literal["BUY", "SELL"]
SymbolType = Literal["SPY", "IWM"]

ExecutionStatus = Literal[
    "SUBMITTED",
    "REJECTED",
    "BLOCKED",
]


# ==================================================
# Time authority
# ==================================================

def now_utc() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ==================================================
# Option specification
# ==================================================

@dataclass(frozen=True)
class OptionSpec:
    expiry: str
    strike: float
    right: Literal["C", "P"]
    multiplier: int = 100

    def __post_init__(self):
        if not self.expiry or len(self.expiry) != 8:
            raise ValueError("Option expiry must be YYYYMMDD")
        if self.strike <= 0:
            raise ValueError("Option strike must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expiry": self.expiry,
            "strike": self.strike,
            "right": self.right,
            "multiplier": self.multiplier,
        }


# ==================================================
# Execution Intent (CANONICAL)
# ==================================================

@dataclass(frozen=True)
class ExecutionIntent:
    """
    Immutable, replay-safe, broker-agnostic trade intent.

    Phase 27:
    - Optional cryptographic linkage to SignalContext
    """

    # Identity
    intent_id: str
    parent_intent_id: Optional[str]
    created_utc: str

    # Instrument
    symbol: SymbolType
    sec_type: SecurityType

    # Order intent
    quantity: int
    action: ActionType

    # Strategy context
    strategy_tag: str

    # Phase 27 — justification linkage (HASH ONLY)
    signal_context_hash: Optional[str] = None

    # Optional option contract
    option: Optional[OptionSpec] = None

    # ----------------------------
    # Validation
    # ----------------------------

    def __post_init__(self):
        if self.symbol not in ("SPY", "IWM"):
            raise ValueError("Only SPY and IWM are permitted symbols")

        if self.quantity <= 0:
            raise ValueError("Quantity must be > 0")

        if self.sec_type == "OPT" and self.option is None:
            raise ValueError("Option intent requires OptionSpec")

        if self.sec_type == "STK" and self.option is not None:
            raise ValueError("Stock intent cannot include OptionSpec")

        if self.action not in ("BUY", "SELL"):
            raise ValueError("Invalid action")

    # ----------------------------
    # Deterministic serialization
    # ----------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "parent_intent_id": self.parent_intent_id,
            "created_utc": self.created_utc,
            "symbol": self.symbol,
            "sec_type": self.sec_type,
            "quantity": self.quantity,
            "action": self.action,
            "strategy_tag": self.strategy_tag,
            "signal_context_hash": self.signal_context_hash,
            "option": self.option.to_dict() if self.option else None,
        }

    # ----------------------------
    # Factory helpers
    # ----------------------------

    @staticmethod
    def new(
        *,
        symbol: SymbolType,
        qty: int,
        action: ActionType,
        sec_type: SecurityType,
        strategy_tag: str,
        option: Optional[OptionSpec] = None,
        signal_context_hash: Optional[str] = None,
    ) -> "ExecutionIntent":
        return ExecutionIntent(
            intent_id=str(uuid.uuid4()),
            parent_intent_id=None,
            created_utc=now_utc(),
            symbol=symbol,
            sec_type=sec_type,
            quantity=qty,
            action=action,
            strategy_tag=strategy_tag,
            signal_context_hash=signal_context_hash,
            option=option,
        )

    def derive_exit(self) -> "ExecutionIntent":
        """
        Derive a deterministic EXIT intent.
        Justification hash is NOT propagated.
        """
        exit_action = "SELL" if self.action == "BUY" else "BUY"

        return ExecutionIntent(
            intent_id=f"{self.intent_id}::EXIT",
            parent_intent_id=self.intent_id,
            created_utc=now_utc(),
            symbol=self.symbol,
            sec_type=self.sec_type,
            quantity=self.quantity,
            action=exit_action,
            strategy_tag="EXIT",
            signal_context_hash=None,
            option=self.option,
        )


# ==================================================
# Execution Result (DOWNSTREAM)
# ==================================================

@dataclass
class ExecutionResult:
    status: ExecutionStatus
    order_id: Optional[int]
    reason: Optional[str]

    executed_utc: str
    parity_hash: Optional[str]

    raw: Dict[str, Any]

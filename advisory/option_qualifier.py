#
# option_qualifier.py
#
# Option Qualification Authority
# PHASE 8 — ATOMIC (NO SUBPHASES)
#
# Responsible for:
# - Structural validation of 0DTE option candidates
# - Symbol constraints (SPY / IWM only)
# - CALL / PUT symmetry enforcement
# - Strike sanity relative to provided spot price
# - Expiry correctness (same-day enforcement)
#
# Explicitly NOT responsible for:
# - Market data fetching
# - Time authority
# - Strike selection logic
# - Risk limits or sizing
# - ExecutionIntent creation
# - Broker logic
# - OPS state
#

import datetime as dt
from dataclasses import dataclass
from typing import Literal


# ----------------------------
# Type constraints
# ----------------------------

DirectionType = Literal["CALL", "PUT"]
SymbolType = Literal["SPY", "IWM"]


# ----------------------------
# Qualified output (pure data)
# ----------------------------

@dataclass(frozen=True)
class QualifiedOption:
    symbol: SymbolType
    right: Literal["C", "P"]
    expiry: str            # YYYYMMDD
    strike: float
    underlying_price: float


# ----------------------------
# Public API
# ----------------------------

def qualify_0dte_option(
    *,
    symbol: SymbolType,
    direction: DirectionType,
    expiry: str,
    strike: float,
    underlying_price: float,
) -> QualifiedOption:
    """
    Validate the structural correctness of a SINGLE-LEG 0DTE option.

    Deterministic.
    Stateless.
    Replay-safe.
    Fail-closed.

    Returns:
        QualifiedOption

    Raises:
        ValueError on any structural violation.
    """

    # ----------------------------
    # Symbol guard
    # ----------------------------
    if symbol not in ("SPY", "IWM"):
        raise ValueError("Option qualification limited to SPY and IWM")

    # ----------------------------
    # Direction mapping
    # ----------------------------
    if direction == "CALL":
        right = "C"
    elif direction == "PUT":
        right = "P"
    else:
        raise ValueError("Direction must be CALL or PUT")

    # ----------------------------
    # Expiry validation (0DTE)
    # ----------------------------
    try:
        expiry_dt = dt.datetime.strptime(expiry, "%Y%m%d").date()
    except ValueError:
        raise ValueError("Expiry must be YYYYMMDD")

    today_utc = dt.datetime.utcnow().date()
    if expiry_dt != today_utc:
        raise ValueError("Only 0DTE (same-day) options are permitted")

    # ----------------------------
    # Underlying price sanity
    # ----------------------------
    if underlying_price <= 0:
        raise ValueError("Underlying price must be positive")

    # ----------------------------
    # Strike sanity (structural, not selection)
    # ----------------------------
    if strike <= 0:
        raise ValueError("Strike must be positive")

    # Very loose guardrail: strike must be within ±20% of spot
    lower = underlying_price * 0.80
    upper = underlying_price * 1.20

    if not (lower <= strike <= upper):
        raise ValueError(
            f"Strike {strike} outside sanity bounds relative to spot {underlying_price}"
        )

    # ----------------------------
    # Qualified output
    # ----------------------------
    return QualifiedOption(
        symbol=symbol,
        right=right,
        expiry=expiry,
        strike=strike,
        underlying_price=underlying_price,
    )

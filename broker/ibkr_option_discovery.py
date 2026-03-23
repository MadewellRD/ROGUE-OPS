#
# ibkr_option_discovery.py
#
# IBKR Option Discovery Authority
# PHASE 9A — ATOMIC (FINAL / DEDUPED)
#
# Responsible for:
# - Discovering REAL option contracts from IBKR
# - Enumerating valid 0DTE options
# - Normalizing and deduplicating broker responses
#
# Explicitly NOT responsible for:
# - Strike preference or selection
# - Delta / gamma / theta logic
# - Risk sizing
# - Execution
# - OPS state
#

import datetime as dt
from dataclasses import dataclass
from typing import Literal, List, Dict

from ibapi.contract import Contract
from ibkr_runtime import get_ibkr_runtime


# ----------------------------
# Type constraints
# ----------------------------

DirectionType = Literal["CALL", "PUT"]
RightType = Literal["C", "P"]
SymbolType = Literal["SPY", "IWM"]


# ----------------------------
# Discovered contract (pure data)
# ----------------------------

@dataclass(frozen=True)
class DiscoveredOption:
    symbol: SymbolType
    expiry: str                  # YYYYMMDD
    strike: float
    right: RightType
    trading_class: str
    conid: int
    multiplier: int


# ----------------------------
# Helpers
# ----------------------------

def _today_utc_yyyymmdd() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d")


def _direction_to_right(direction: DirectionType) -> RightType:
    if direction == "CALL":
        return "C"
    if direction == "PUT":
        return "P"
    raise ValueError("Direction must be CALL or PUT")


# ----------------------------
# Public API
# ----------------------------

def discover_0dte_options(
    *,
    symbol: SymbolType,
    direction: DirectionType,
    spot: float,
    strike_window_pct: float = 0.10,
) -> List[DiscoveredOption]:
    """
    Discover REAL 0DTE option contracts for a symbol from IBKR.

    Deterministic given identical IBKR responses.
    Deduplicated by conId (canonical broker identity).
    Fail-closed.
    """

    if symbol not in ("SPY", "IWM"):
        raise ValueError("IBKR option discovery limited to SPY and IWM")

    runtime = get_ibkr_runtime()

    expiry = _today_utc_yyyymmdd()
    right = _direction_to_right(direction)

    lower = spot * (1.0 - strike_window_pct)
    upper = spot * (1.0 + strike_window_pct)

    # ----------------------------
    # IBKR-compliant partial contract
    # ----------------------------

    c = Contract()
    c.symbol = symbol
    c.secType = "OPT"
    c.exchange = "SMART"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = expiry
    c.right = right

    details = runtime.request_contract_details(c)

    if not details:
        raise RuntimeError("IBKR returned no option contracts")

    # ----------------------------
    # Deduplication by conId
    # ----------------------------

    by_conid: Dict[int, DiscoveredOption] = {}

    for d in details:
        cd = d.contract

        if cd.conId <= 0:
            continue

        if cd.strike <= 0:
            continue

        if not (lower <= cd.strike <= upper):
            continue

        if cd.conId in by_conid:
            continue  # HARD DEDUPE (institutional requirement)

        by_conid[cd.conId] = DiscoveredOption(
            symbol=cd.symbol,
            expiry=cd.lastTradeDateOrContractMonth,
            strike=cd.strike,
            right=cd.right,
            trading_class=cd.tradingClass or cd.symbol,
            conid=cd.conId,
            multiplier=int(cd.multiplier) if cd.multiplier else 100,
        )

    if not by_conid:
        raise RuntimeError("No 0DTE options found after filtering")

    # ----------------------------
    # Deterministic ordering
    # ----------------------------

    discovered = list(by_conid.values())
    discovered.sort(key=lambda o: o.strike)

    return discovered

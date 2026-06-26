#
# replay_option_discovery.py
#
# Replay / Backtest Option Discovery Adapter
# PHASE 17 — ATOMIC (NO SUBPHASES)
#
# Responsible for:
# - Providing deterministic option discovery during REPLAY / BACKTEST
# - Emitting the SAME DiscoveredOption objects as IBKR discovery
#
# Explicitly NOT responsible for:
# - Strike preference
# - Greeks
# - Risk
# - Execution
# - Market data fetching
#

from typing import List, Literal

from ibkr_option_discovery import DiscoveredOption


# ----------------------------
# Type constraints
# ----------------------------

DirectionType = Literal["CALL", "PUT"]
SymbolType = Literal["SPY", "IWM"]


# ----------------------------
# Public API
# ----------------------------

def replay_discover_0dte_options(
    *,
    symbol: SymbolType,
    direction: DirectionType,
    expiry: str,
    strikes: List[float],
    multiplier: int = 100,
) -> List[DiscoveredOption]:
    """
    Deterministic replay option discovery.

    This function simulates IBKR discovery by
    emitting DiscoveredOption objects from known strikes.

    Inputs MUST be deterministic and historically sourced.

    Args:
        symbol      : SPY or IWM
        direction   : CALL or PUT
        expiry      : YYYYMMDD (0DTE relative to replay time)
        strikes     : List of available strikes at that time
        multiplier  : Contract multiplier (default 100)

    Returns:
        List[DiscoveredOption]
    """

    if symbol not in ("SPY", "IWM"):
        raise ValueError("Replay discovery limited to SPY and IWM")

    if direction == "CALL":
        right = "C"
    elif direction == "PUT":
        right = "P"
    else:
        raise ValueError("Direction must be CALL or PUT")

    discovered: List[DiscoveredOption] = []

    for strike in strikes:
        if strike <= 0:
            continue

        discovered.append(
            DiscoveredOption(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                right=right,
                trading_class=symbol,
                conid=hash((symbol, expiry, strike, right)) & 0xFFFFFFFF,
                multiplier=multiplier,
            )
        )

    if not discovered:
        raise RuntimeError("Replay discovery produced no option contracts")

    # Deterministic ordering
    discovered.sort(key=lambda o: o.strike)

    return discovered

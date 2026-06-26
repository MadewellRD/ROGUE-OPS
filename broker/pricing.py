#
# broker/pricing.py
#
# Broker-agnostic order pricing helpers.
#
# Marketable-limit pricing replaces naked market orders on instruments with
# wide/gappy spreads (notably 0DTE options). A marketable limit fills like a
# market order in normal conditions but caps the worst price you'll accept, so
# a blown-out spread or a bad print can't fill you at an arbitrary level.
#

from typing import Optional


class UnpriceableError(ValueError):
    """Raised when no usable quote exists to build a limit price (fail-closed)."""


def round_to_tick(price: float, tick: float = 0.01) -> float:
    """Round a price to the nearest tick (default penny)."""
    if tick <= 0:
        return round(price, 2)
    return round(round(price / tick) * tick, 2)


def marketable_limit(
    side: str,
    bid: Optional[float],
    ask: Optional[float],
    *,
    buffer_pct: float = 0.0,
    tick: float = 0.01,
) -> float:
    """
    Compute a marketable limit price.

    BUY  -> price at the ask (optionally + buffer_pct), so it crosses and fills
            but never pays more than ask*(1+buffer_pct).
    SELL -> price at the bid (optionally - buffer_pct), symmetric floor.

    Raises UnpriceableError if the needed side of the book is missing/non-positive
    (caller should fail closed rather than fall back to a naked market order).
    """
    side = side.upper()
    if side == "BUY":
        ref = ask
        if ref is None or ref <= 0:
            raise UnpriceableError("no ask to build a BUY limit")
        return round_to_tick(ref * (1.0 + buffer_pct), tick)
    if side == "SELL":
        ref = bid
        if ref is None or ref <= 0:
            raise UnpriceableError("no bid to build a SELL limit")
        return round_to_tick(ref * (1.0 - buffer_pct), tick)
    raise ValueError(f"unknown side: {side!r}")

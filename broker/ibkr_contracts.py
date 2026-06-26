from typing import Dict, Optional
from ibapi.contract import Contract

_CONID_CACHE: Dict[str, int] = {}


def get_cached_conid(symbol: str) -> Optional[int]:
    return _CONID_CACHE.get(symbol)


def cache_conid(symbol: str, conid: int):
    _CONID_CACHE[symbol] = conid


def build_stock_contract(symbol: str) -> Contract:
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.exchange = "SMART"
    c.primaryExchange = "NASDAQ" if symbol in ("QQQ",) else "NYSE"
    c.currency = "USD"
    return c


def build_option_contract(symbol: str, option) -> Contract:
    """
    Build a fully-specified IBKR OPT contract from an OptionSpec.

    A fully-specified option (symbol + expiry + strike + right + multiplier)
    is directly placeable; no conId round-trip is required for submission.
    `option` is execution.execution_contracts.OptionSpec.
    """
    c = Contract()
    c.symbol = symbol
    c.secType = "OPT"
    c.exchange = "SMART"
    c.currency = "USD"
    c.lastTradeDateOrContractMonth = option.expiry   # YYYYMMDD
    c.strike = float(option.strike)
    c.right = option.right                            # "C" / "P"
    c.multiplier = str(option.multiplier)
    return c

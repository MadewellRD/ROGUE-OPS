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

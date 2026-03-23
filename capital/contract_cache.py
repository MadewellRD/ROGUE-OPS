#
# contract_cache.py
#
# One-time contract qualification + in-memory cache
#

from typing import Dict, Optional

_CONTRACT_CACHE: Dict[str, int] = {}


def get_cached_conid(symbol: str) -> Optional[int]:
    return _CONTRACT_CACHE.get(symbol)


def cache_conid(symbol: str, conid: int):
    _CONTRACT_CACHE[symbol] = conid


def clear_contract_cache():
    _CONTRACT_CACHE.clear()

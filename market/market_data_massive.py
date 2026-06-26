#
# market/market_data_massive.py
#
# Massive (massive.com) REST client — Polygon-compatible US market data.
#
# ROLE: HISTORICAL / daily data source — backtesting, daily indicators,
# reference data, and option daily marks. The LIVE intraday feed remains IBKR;
# this module does not touch the live execution path.
#
# Plan note: the current key is entitled to DAILY aggregates (stocks + options)
# + reference. Real-time snapshot / last-trade / NBBO and intraday bars require
# a plan upgrade and return MassiveNotEntitled (HTTP 403) until then.
#
# Auth: Bearer token. Base: MASSIVE_BASE_URL (default https://api.massive.com).
# Key: explicit arg -> MASSIVE_API_KEY -> MASSIVE_API_KEY_FILE -> ops_home/massive_key.txt
#

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_BASE = "https://api.massive.com"


class MassiveError(RuntimeError):
    pass


class MassiveNotEntitled(MassiveError):
    """HTTP 403 — the current plan does not include this data (real-time/NBBO/intraday)."""


@dataclass(frozen=True)
class Bar:
    t_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None

    @property
    def date(self) -> str:
        import datetime as dt
        return (
            dt.datetime.fromtimestamp(self.t_ms / 1000, tz=dt.timezone.utc)
            .date()
            .isoformat()
        )


def _base() -> str:
    return os.getenv("MASSIVE_BASE_URL", DEFAULT_BASE).rstrip("/")


def _resolve_key(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    env = os.getenv("MASSIVE_API_KEY")
    if env:
        return env
    path = os.getenv("MASSIVE_API_KEY_FILE")
    if not path:
        # Repo-relative key file: consistent whether run by the user or a
        # service account; gitignored so it is never committed.
        path = str(Path(__file__).resolve().parents[1] / ".massive_key")
    if path and os.path.isfile(path):
        return Path(path).read_text(encoding="utf-8").strip()
    raise MassiveError(
        "No Massive API key (set MASSIVE_API_KEY, MASSIVE_API_KEY_FILE, or create .massive_key)."
    )


def _get(path: str, *, api_key: Optional[str] = None, timeout: float = 10) -> Dict[str, Any]:
    url = _base() + path
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {_resolve_key(api_key)}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 403:
            raise MassiveNotEntitled(f"403 {path}: {body[:200]}")
        raise MassiveError(f"HTTP {e.code} {path}: {body[:200]}")
    except urllib.error.URLError as e:
        raise MassiveError(f"network error {path}: {e}")


def parse_aggs(raw: Dict[str, Any]) -> List[Bar]:
    """Pure parser for a Polygon/Massive aggregates response. Testable offline."""
    bars: List[Bar] = []
    for r in (raw.get("results") or []):
        try:
            bars.append(Bar(
                t_ms=int(r["t"]),
                open=float(r["o"]), high=float(r["h"]), low=float(r["l"]), close=float(r["c"]),
                volume=float(r.get("v", 0) or 0),
                vwap=(float(r["vw"]) if r.get("vw") is not None else None),
            ))
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed rows, never crash
    bars.sort(key=lambda b: b.t_ms)
    return bars


# ==================================================
# Public (historical) API
# ==================================================

def daily_bars(symbol: str, date_from: str, date_to: str, *, api_key: Optional[str] = None) -> List[Bar]:
    """Daily OHLCV bars for a stock/ETF over [date_from, date_to] (YYYY-MM-DD)."""
    raw = _get(
        f"/v2/aggs/ticker/{urllib.parse.quote(symbol)}/range/1/day/{date_from}/{date_to}",
        api_key=api_key,
    )
    return parse_aggs(raw)


def option_prev_bar(option_ticker: str, *, api_key: Optional[str] = None) -> Optional[Bar]:
    """Previous-day OHLCV for an option contract (e.g. O:SPY260626C00734000)."""
    bars = parse_aggs(_get(f"/v2/aggs/ticker/{urllib.parse.quote(option_ticker)}/prev", api_key=api_key))
    return bars[-1] if bars else None


def reference(symbol: str, *, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Reference data for a ticker (name, exchange, type, figi, ...)."""
    return _get(f"/v3/reference/tickers/{urllib.parse.quote(symbol)}", api_key=api_key).get("results", {})

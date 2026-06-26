#
# market_data_adapter_steady.py
#
# SteadyAPI → MarketSnapshot Adapter
# PHASE 28 — NORMALIZED INGESTION (FINAL)
#
# SPOT SOURCE OF TRUTH:
# - /v1/markets/stock/quotes
# - Best-available real-time price (priority-based)
#
# SESSION:
# - Derived from market-info
# - Contextual only (NOT price-gating)
#

from typing import Literal
import datetime as dt
import time
import requests

from market.market_data import MarketSnapshot
from market.market_data_normalizer import normalize_market_data


# ==================================================
# Configuration
# ==================================================

STEADYAPI_BASE_URL = "https://api.steadyapi.com"

STEADY_SOURCE_MAP = {
    "PAPER": "PAPER",
    "LIVE": "LIVE",
}

REQUEST_TIMEOUT_SECONDS = 5
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.25


# ==================================================
# Internal helpers (TRANSPORT ONLY)
# ==================================================

def _get_with_retry(url: str, *, headers: dict, params: dict | None = None):
    """
    Bounded retry helper.

    Retries ONLY on network timeout.
    All other failures propagate immediately.
    """

    last_exc = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp

        except requests.exceptions.Timeout as e:
            last_exc = e
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS)
            else:
                raise RuntimeError(
                    f"SteadyAPI timeout after {MAX_ATTEMPTS} attempts"
                ) from e

    # Defensive (should never reach)
    raise last_exc  # type: ignore


# ==================================================
# Public API
# ==================================================

def get_market_snapshot(
    *,
    symbol: str,
    source: Literal["PAPER", "LIVE"],
    api_key: str,
) -> MarketSnapshot:
    """
    Fetch real-time SPOT price and market session from SteadyAPI
    and emit a canonical MarketSnapshot.

    Fail-closed. Deterministic. Replay-safe.
    """

    if not api_key:
        raise RuntimeError("SteadyAPI key not provided to adapter")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # --------------------------------------------------
    # Market session (CONTEXT ONLY)
    # --------------------------------------------------

    session_resp = _get_with_retry(
        f"{STEADYAPI_BASE_URL}/v2/markets/market-info",
        headers=headers,
    )

    mrkt_status = session_resp.json().get("body", {}).get("mrktStatus")

    if mrkt_status == "Pre-Market":
        session = "PRE"
    elif mrkt_status == "Open":
        session = "REGULAR"
    elif mrkt_status == "After-Hours":
        session = "POST"
    else:
        session = "CLOSED"

    # --------------------------------------------------
    # Real-time Quote (AUTHORITATIVE SPOT)
    # --------------------------------------------------

    quotes_resp = _get_with_retry(
        f"{STEADYAPI_BASE_URL}/v1/markets/stock/quotes",
        headers=headers,
        params={"ticker": symbol},
    )

    quotes = quotes_resp.json().get("body", [])
    if not quotes:
        raise RuntimeError("SteadyAPI quotes returned empty body")

    quote = quotes[0]

    # --------------------------------------------------
    # SPOT SELECTION — PRIORITY-BASED
    # --------------------------------------------------

    spot = None
    ts = None

    if quote.get("regularMarketPrice"):
        spot = quote["regularMarketPrice"]
        ts = quote.get("regularMarketTime")

    elif quote.get("preMarketPrice"):
        spot = quote["preMarketPrice"]
        ts = quote.get("preMarketTime")

    elif quote.get("postMarketPrice"):
        spot = quote["postMarketPrice"]
        ts = quote.get("postMarketTime")

    elif quote.get("lastSalePrice"):
        try:
            spot = (
                str(quote["lastSalePrice"])
                .replace("$", "")
                .replace(",", "")
            )
            spot = float(spot)
            ts = (
                quote.get("regularMarketTime")
                or quote.get("preMarketTime")
                or quote.get("postMarketTime")
            )
        except Exception:
            spot = None

    if spot is None or float(spot) <= 0:
        raise RuntimeError(
            f"No valid SPOT price "
            f"(session={session}, quoteState={quote.get('marketState')})"
        )

    spot = float(spot)

    # --------------------------------------------------
    # Timestamp (UTC, authoritative)
    # --------------------------------------------------

    if ts:
        timestamp_utc = (
            dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc)
            .replace(microsecond=0)
        )
    else:
        timestamp_utc = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)

    # --------------------------------------------------
    # Normalization Authority (SEALED)
    # --------------------------------------------------

    # --------------------------------------------------
    # OHLCV (Phase 4) — best-effort from the quote payload
    # --------------------------------------------------

    def _num(*keys):
        for k in keys:
            v = quote.get(k)
            if v is not None:
                try:
                    return float(str(v).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    continue
        return None

    high = _num("regularMarketDayHigh", "dayHigh", "high")
    low = _num("regularMarketDayLow", "dayLow", "low")
    prev_close = _num("regularMarketPreviousClose", "previousClose", "prevClose")
    volume = _num("regularMarketVolume", "volume")

    return normalize_market_data(
        symbol=symbol,
        spot=spot,
        timestamp_utc=timestamp_utc,
        session=session,
        source=STEADY_SOURCE_MAP[source],
        high=high,
        low=low,
        prev_close=prev_close,
        volume=volume,
    )

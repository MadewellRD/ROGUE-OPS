# api_clients.py
#
# External Data & Indicator Authority Clients
#
# PHASE 28 — INDICATOR ASSERTION CONSTRUCTION (ATOMIC)
# PHASE 30 — VWAP AUTHORITY CONSUMPTION (ATOMIC)
# PHASE 36 — ATR AUTHORITY CONSUMPTION (LOCAL, REQUIRED)
# PHASE 38 — AAVWAP AUTHORITY CONSUMPTION (ATOMIC)
# PHASE 40 — LEVEL AUTHORITY CONSUMPTION (ADVISORY)
#
# BROKERAGE-GRADE RULES:
# - Vendor indicators are fetched, never recomputed
# - Indicators are REAL or ABSENT
# - REQUIRED indicators missing → FAIL CLOSED
#

import requests
import datetime as dt

from advisory.indicator_authority import create_indicator_assertion
from advisory.vwap_authority import OHLCVBar, compute_vwap
from advisory.aavwap_authority import OHLCVBar as AAVWAPBar, compute_aavwap
from advisory.atr_authority import OHLCBar, compute_atr
from advisory.level_authority import (
    OHLCBar as LevelBar,
    compute_prior_day_levels,
    compute_opening_range,
)

STEADYAPI_BASE_URL = "https://api.steadyapi.com"

# Canonical indicator request parameters (vendor-aligned)
RSI_INTERVAL = "5m"
RSI_PERIODS = (7, 14)
RSI_LIMIT = 50

EMA_INTERVAL = "5m"
EMA_PERIODS = (9, 21)
EMA_LIMIT = 50

MACD_INTERVAL = "5m"
MACD_LIMIT = 50


# ==================================================
# Helpers
# ==================================================

def _parse_bar_timestamp(bar: dict) -> dt.datetime:
    for key in ("date", "datetime", "timestamp", "time"):
        if key in bar:
            return (
                dt.datetime.fromisoformat(str(bar[key]).replace("Z", "+00:00"))
                .astimezone(dt.timezone.utc)
                .replace(microsecond=0)
            )
    raise KeyError("No valid timestamp field found in bar")


def _session_open_utc(ts: dt.datetime) -> dt.datetime:
    return ts.replace(hour=13, minute=30, second=0, microsecond=0)


# ==================================================
# Indicator Aggregation (AUTHORITATIVE)
# ==================================================

def fetch_and_aggregate_indicators(*, api_key: str, ticker: str):

    print(f"  [PROCESS] Aggregating indicators for {ticker} (Steady authoritative)")

    if not api_key:
        raise RuntimeError("SteadyAPI key not provided")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    required = {}
    advisory = {}

    # --------------------------------------------------
    # RSI — VENDOR (REQUIRED)
    # --------------------------------------------------
    for period in RSI_PERIODS:
        resp = requests.get(
            f"{STEADYAPI_BASE_URL}/v1/markets/indicators/rsi",
            headers=headers,
            params={
                "ticker": ticker,
                "interval": RSI_INTERVAL,
                "time_period": str(period),
                "series_type": "close",
                "limit": str(RSI_LIMIT),
            },
            timeout=10,
        )

        if not resp.ok:
            raise RuntimeError(f"RSI({period}) unavailable: {resp.text}")

        body = resp.json().get("body", [])
        if not body:
            raise RuntimeError(f"RSI({period}) returned empty body")

        required[f"RSI({period})"] = float(body[-1]["RSI"])
        print(f"    - RSI({period}): {required[f'RSI({period})']}")

    # --------------------------------------------------
    # EMA — VENDOR (REQUIRED)
    # --------------------------------------------------
    for period in EMA_PERIODS:
        resp = requests.get(
            f"{STEADYAPI_BASE_URL}/v1/markets/indicators/ema",
            headers=headers,
            params={
                "ticker": ticker,
                "interval": EMA_INTERVAL,
                "time_period": str(period),
                "series_type": "close",
                "limit": str(EMA_LIMIT),
            },
            timeout=10,
        )

        if not resp.ok:
            raise RuntimeError(f"EMA({period}) unavailable: {resp.text}")

        body = resp.json().get("body", [])
        if not body:
            raise RuntimeError(f"EMA({period}) returned empty body")

        required[f"EMA({period})"] = float(body[-1]["EMA"])
        print(f"    - EMA({period}): {required[f'EMA({period})']}")

    # --------------------------------------------------
    # MACD — VENDOR (REQUIRED)
    # --------------------------------------------------
    resp = requests.get(
        f"{STEADYAPI_BASE_URL}/v1/markets/indicators/macd",
        headers=headers,
        params={
            "ticker": ticker,
            "interval": MACD_INTERVAL,
            "fast_period": "12",
            "slow_period": "26",
            "signal_period": "9",
            "series_type": "close",
            "limit": str(MACD_LIMIT),
        },
        timeout=10,
    )

    if not resp.ok:
        raise RuntimeError(f"MACD unavailable: {resp.text}")

    body = resp.json().get("body", [])
    if not body:
        raise RuntimeError("MACD returned empty body")

    # ✅ Correct SteadyAPI field
    required["MACD"] = float(body[-1]["MACD_Hist"])
    print(f"    - MACD Histogram: {required['MACD']}")

    # --------------------------------------------------
    # Historical Bars — REQUIRED (VWAP / ATR)
    # --------------------------------------------------
    hist = requests.get(
        f"{STEADYAPI_BASE_URL}/v2/markets/stock/history",
        headers=headers,
        params={"ticker": ticker, "interval": "1m", "limit": "390"},
        timeout=10,
    )

    if not hist.ok:
        raise RuntimeError(f"Historical bars unavailable: {hist.text}")

    bars = hist.json().get("body", [])
    if not bars:
        raise RuntimeError("No historical bars returned")

    ohlcv = []
    atr_bars = []

    for b in bars:
        ts = _parse_bar_timestamp(b)
        close = float(str(b["close"]).replace(",", ""))

        ohlcv.append(
            OHLCVBar(
                timestamp_utc=ts,
                open=float(b["open"]),
                high=float(b["high"]),
                low=float(b["low"]),
                close=close,
                volume=int(b["volume"]),
            )
        )

        atr_bars.append(
            OHLCBar(
                high=float(b["high"]),
                low=float(b["low"]),
                close=close,
            )
        )

    ohlcv.sort(key=lambda x: x.timestamp_utc, reverse=True)
    spot = ohlcv[0].close

    vwap = compute_vwap(bars=ohlcv, spot_price=spot, session="REGULAR")
    required["VWAP"] = vwap.position
    advisory["VWAP_Price"] = vwap.vwap_price
    print(f"    - VWAP: {vwap.vwap_price} ({vwap.position})")

    atr = compute_atr(bars=atr_bars)
    required["ATR"] = atr.atr_value
    advisory["ATR_State"] = atr.atr_state
    print(f"    - ATR(14): {atr.atr_value} ({atr.atr_state})")

    assertion = create_indicator_assertion(
        required=required,
        advisory=advisory,
    )

    print("  [OK] IndicatorAssertion created")
    print(f"    - Assertion hash: {assertion.assertion_hash}")

    return assertion

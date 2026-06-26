#
# tools/test_indicators.py
#
# Unit tests for the enriched IndicatorEngine (Phase 4): ATR + VWAP from OHLCV.
#   python tools\test_indicators.py
#

import sys
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data import MarketSnapshot
from advisory.indicator_engine import IndicatorEngine

NOW = dt.datetime(2026, 6, 25, 15, 0, 0, tzinfo=dt.timezone.utc)


def _snap(spot, with_ohlcv=True, vol=1_000_000):
    meta = None
    if with_ohlcv:
        meta = {"high": spot + 1.0, "low": spot - 1.0, "prev_close": spot - 0.1, "volume": vol}
    return MarketSnapshot(symbol="SPY", spot=spot, session="REGULAR",
                          timestamp_utc=NOW, source="SIM", meta=meta)


def main() -> None:
    # --- With OHLCV + oscillating prices: all required indicators compute ---
    eng = IndicatorEngine()
    p = 500.0
    a = None
    for i in range(40):
        p += 0.5 if (i % 2 == 0) else -0.3   # net up, but real losses each odd tick
        a = eng.update(_snap(round(p, 2), with_ohlcv=True, vol=1_000_000 + i * 10_000))

    req = a.required
    assert req["ATR"] is not None, "ATR should compute from high/low/prev_close"
    assert req["VWAP_Position"] in ("above", "below"), f"VWAP_Position: {req['VWAP_Position']}"
    assert a.advisory["VWAP"] is not None, "VWAP should compute from volume"
    assert req["RSI(7)"] is not None and req["RSI(14)"] is not None, "RSI should compute"
    assert req["MACD_Histogram"] is not None, "MACD histogram should compute"
    assert a.required_passed, f"all required present -> required_passed True; got {req}"

    # ATR sanity: true range of a 2-wide band is ~2
    assert 1.0 <= req["ATR"] <= 3.0, f"ATR out of expected band: {req['ATR']}"

    # --- Fail-closed: no OHLCV -> ATR/VWAP None -> required_passed False ---
    eng2 = IndicatorEngine()
    b = None
    for i in range(5):
        b = eng2.update(_snap(500.0 + i, with_ohlcv=False))
    assert b.required["ATR"] is None, "no high/low -> ATR None"
    assert b.required["VWAP_Position"] is None, "no volume -> VWAP_Position None"
    assert not b.required_passed, "missing required indicators -> no signal (fail-closed)"

    print("INDICATORS PASS — ATR/VWAP computed from OHLCV; fail-closed without it")


if __name__ == "__main__":
    main()

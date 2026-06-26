#
# tools/test_massive_client.py
#
# Offline unit test for the Massive client's aggregate parser (no network).
#   python tools\test_massive_client.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_massive import parse_aggs

# Recorded from the live Massive API (SPY daily aggregates), trimmed.
SAMPLE = {
    "ticker": "SPY",
    "results": [
        {"v": 4.3049e7, "vw": 722.093, "o": 721.25, "c": 720.65, "h": 724.87, "l": 720.47, "t": 1777608000000, "n": 625196},
        {"v": 5.1950e7, "vw": 718.566, "o": 720.07, "c": 718.01, "h": 722.12, "l": 714.99, "t": 1777867200000, "n": 772768},
    ],
    "status": "OK",
}


def main() -> None:
    bars = parse_aggs(SAMPLE)
    assert len(bars) == 2, "two bars expected"
    assert bars[0].t_ms < bars[1].t_ms, "bars must be sorted ascending by time"
    last = bars[-1]
    assert last.close == 718.01 and last.high == 722.12 and last.low == 714.99, "OHLC mapping"
    assert last.vwap == 718.566, "vwap mapping"
    assert last.date == "2026-05-04", f"date derivation: {last.date}"

    # Robust to empty / malformed payloads (never crash).
    assert parse_aggs({"results": []}) == []
    assert parse_aggs({}) == []
    assert parse_aggs({"results": [{"t": 1, "o": 1.0}]}) == [], "malformed row skipped"

    print("MASSIVE CLIENT PASS — daily aggregate parsing (sorted, typed, robust)")


if __name__ == "__main__":
    main()

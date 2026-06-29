#
# tools/test_massive_intraday.py
#
# Offline test for the Massive intraday adapter (no network): builds the correct
# range path and parses sorted bars. The HTTP layer (_get) is mocked.
#
#   python tools\test_massive_intraday.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market import market_data_massive as M

CANNED = {"results": [
    {"t": 1700000300000, "o": 100.5, "h": 102, "l": 100, "c": 101.5, "v": 1200},
    {"t": 1700000000000, "o": 100.0, "h": 101, "l": 99, "c": 100.5, "v": 1000, "vw": 100.2},
]}


def test_intraday_bars_path_and_parse():
    captured = {}
    orig = M._get

    def fake(path, *, api_key=None, timeout=10):
        captured["path"] = path
        return CANNED

    M._get = fake
    try:
        bars = M.intraday_bars("SPY", "2026-06-01", "2026-06-27", multiplier=5, timespan="minute")
    finally:
        M._get = orig

    assert "/range/5/minute/2026-06-01/2026-06-27" in captured["path"], captured["path"]
    assert "sort=asc" in captured["path"]
    assert len(bars) == 2
    # parse_aggs sorts by t_ms ascending
    assert bars[0].t_ms < bars[1].t_ms
    assert bars[0].close == 100.5 and bars[1].close == 101.5


def main() -> None:
    test_intraday_bars_path_and_parse()
    print("MASSIVE INTRADAY PASS — intraday_bars builds the range path and parses sorted bars")


if __name__ == "__main__":
    main()

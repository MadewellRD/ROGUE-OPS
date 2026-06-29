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


def test_keep_rth_filters_to_regular_session():
    import datetime as dt
    from research.intraday import keep_rth

    def ms(y, mo, d, h, mi):
        return int(dt.datetime(y, mo, d, h, mi, tzinfo=dt.timezone.utc).timestamp() * 1000)

    def bar(t, c):
        return M.Bar(t_ms=t, open=c, high=c, low=c, close=c, volume=1)

    bars = [
        bar(ms(2026, 6, 24, 14, 0), 1.0),   # Wed 10:00 EDT -> keep
        bar(ms(2026, 6, 24, 13, 30), 2.0),  # Wed 09:30 EDT -> keep (open, inclusive)
        bar(ms(2026, 6, 24, 12, 0), 9.0),   # Wed 08:00 EDT -> drop (pre-market)
        bar(ms(2026, 6, 24, 20, 0), 9.0),   # Wed 16:00 EDT -> drop (close, exclusive)
        bar(ms(2026, 6, 27, 14, 0), 9.0),   # Sat           -> drop (weekend)
        bar(ms(2026, 1, 7, 14, 30), 3.0),   # Wed 09:30 EST -> keep (DST off)
        bar(ms(2026, 1, 7, 14, 0), 9.0),    # Wed 09:00 EST -> drop (pre-market)
    ]
    closes = sorted(b.close for b in keep_rth(bars))
    assert closes == [1.0, 2.0, 3.0], closes


def main() -> None:
    test_intraday_bars_path_and_parse()
    test_keep_rth_filters_to_regular_session()
    print("MASSIVE INTRADAY PASS — intraday_bars range path/parse + RTH filter (EDT/EST, weekend, open/close bounds)")


if __name__ == "__main__":
    main()

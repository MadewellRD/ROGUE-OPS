#
# tools/test_paper_ibkr.py
#
# Offline tests for the IBKR live snapshot feed (no ibapi, no broker):
#   - snapshot_from_bars maps the latest bar -> canonical MarketSnapshot + OHLCV,
#   - IBKRSnapshotProvider throttles fetches, de-dupes by bar timestamp, emits on
#     a new bar, and is fail-soft (fetch error -> None, never raises).
#
#   python tools\test_paper_ibkr.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_ibkr_live import snapshot_from_bars, IBKRSnapshotProvider
from market.market_data_massive import Bar


def test_snapshot_from_bars():
    bars = [
        Bar(t_ms=60_000, open=99.0, high=100.0, low=98.0, close=99.5, volume=500),
        Bar(t_ms=120_000, open=99.5, high=101.0, low=99.0, close=100.7, volume=800),
    ]
    s = snapshot_from_bars("SPY", bars, source="PAPER")
    assert s is not None
    assert abs(s.spot - 100.7) < 1e-9, s.spot
    assert s.source == "PAPER"
    assert s.session in ("PRE", "REGULAR", "POST", "CLOSED")
    meta = getattr(s, "meta", {}) or {}
    assert meta.get("high") == 101.0 and meta.get("low") == 99.0
    assert meta.get("prev_close") == 99.5 and meta.get("volume") == 800.0
    assert snapshot_from_bars("SPY", []) is None


def test_provider_throttle_dedupe_failsoft():
    t = [1000.0]
    calls = {"n": 0}
    state = {"bars": [Bar(t_ms=60_000, open=100, high=100.5, low=99.5, close=100.0, volume=1000)],
             "raise": False}

    def fetch(sym, duration=None, bar_size=None):
        calls["n"] += 1
        if state["raise"]:
            raise RuntimeError("boom")
        return list(state["bars"])

    p = IBKRSnapshotProvider("SPY", fetch_fn=fetch, clock=lambda: t[0], refetch_sec=20.0)

    # first call: fetch + emit
    s1 = p("SPY")
    assert s1 is not None and abs(s1.spot - 100.0) < 1e-9
    assert calls["n"] == 1

    # immediate second call: throttled (no fetch, no emit)
    assert p("SPY") is None and calls["n"] == 1

    # past the throttle, same bar -> fetch happens but de-duped -> None
    t[0] += 21
    assert p("SPY") is None and calls["n"] == 2

    # new bar -> emit
    t[0] += 21
    state["bars"].append(Bar(t_ms=120_000, open=101, high=101.5, low=100.5, close=101.0, volume=1100))
    s2 = p("SPY")
    assert s2 is not None and abs(s2.spot - 101.0) < 1e-9 and calls["n"] == 3

    # fail-soft: a raising fetch yields None, never an exception
    t[0] += 21
    state["raise"] = True
    assert p("SPY") is None


def test_warmup_snapshots():
    bars = [
        Bar(t_ms=60_000, open=99.0, high=100.0, low=98.0, close=99.5, volume=500),
        Bar(t_ms=120_000, open=99.5, high=101.0, low=99.0, close=100.7, volume=800),
        Bar(t_ms=180_000, open=100.7, high=101.5, low=100.0, close=101.2, volume=900),
    ]
    p = IBKRSnapshotProvider("SPY", fetch_fn=lambda s, duration=None, bar_size=None: list(bars))
    seeds = p.warmup_snapshots()
    # all-but-last, ordered; the latest bar is left for the live loop (no double-count)
    assert len(seeds) == 2, len(seeds)
    assert abs(seeds[0].spot - 99.5) < 1e-9 and abs(seeds[1].spot - 100.7) < 1e-9
    # empty / single-bar inputs -> nothing to pre-warm without leaving the latest out
    assert IBKRSnapshotProvider("SPY", fetch_fn=lambda s, d=None, bar_size=None: []).warmup_snapshots() == []
    assert IBKRSnapshotProvider("SPY", fetch_fn=lambda s, d=None, bar_size=None: [bars[0]]).warmup_snapshots() == []
    # fail-soft: a raising fetch yields [] (never blocks startup)
    def _boom(s, duration=None, bar_size=None):
        raise RuntimeError("boom")
    assert IBKRSnapshotProvider("SPY", fetch_fn=_boom).warmup_snapshots() == []


def main() -> None:
    test_snapshot_from_bars()
    test_provider_throttle_dedupe_failsoft()
    test_warmup_snapshots()
    print("PAPER IBKR PASS — snapshot_from_bars OHLCV, provider throttle/dedupe/new-bar/fail-soft, seed-warmup")


if __name__ == "__main__":
    main()

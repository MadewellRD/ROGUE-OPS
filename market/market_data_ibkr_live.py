#
# market/market_data_ibkr_live.py
#
# IBKR LIVE snapshot feed for the autonomy loop (replaces Steady for PAPER/LIVE).
#
# The loop needs OHLCV per bar to drive the IndicatorEngine, so we source the
# most recent intraday bars from IBKR (reqHistoricalData via fetch_bars) and emit
# the latest completed bar as a MarketSnapshot. A small provider throttles the
# IBKR requests and de-duplicates by bar timestamp, so the IndicatorEngine only
# advances on genuinely new bars.
#
# IMPORTANT: this module must stay importable WITHOUT ibapi (so it runs in CI).
# The ibapi-dependent fetch is imported lazily inside the provider; the pure
# transform `snapshot_from_bars` has no broker dependency and is unit-tested.
#
# Config (env): IBKR_HOST, IBKR_PORT (Gateway paper = 4002), IBKR_BAR_SIZE,
# IBKR_DURATION, IBKR_REFETCH_SEC.
#

import datetime as dt
import time
from typing import Callable, List, Optional

from market.market_data import MarketSnapshot
from market.market_data_normalizer import normalize_market_data


def _session_et(now: Optional[dt.datetime] = None) -> str:
    """Best-effort US-equity session from ET wall-clock. Context only (never
    price-gating). Fails soft to REGULAR if tz data is unavailable."""
    try:
        from zoneinfo import ZoneInfo
        now = now or dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return "REGULAR"
    if now.weekday() >= 5:
        return "CLOSED"
    t = now.time()
    if dt.time(4, 0) <= t < dt.time(9, 30):
        return "PRE"
    if dt.time(9, 30) <= t < dt.time(16, 0):
        return "REGULAR"
    if dt.time(16, 0) <= t < dt.time(20, 0):
        return "POST"
    return "CLOSED"


def snapshot_from_bars(symbol: str, bars: List, *, source: str = "PAPER",
                       now: Optional[dt.datetime] = None) -> Optional[MarketSnapshot]:
    """Pure transform: latest IBKR bar -> canonical MarketSnapshot with OHLCV.
    Returns None if there are no bars. No broker dependency (CI-safe)."""
    if not bars:
        return None
    last = bars[-1]
    prev_close = bars[-2].close if len(bars) >= 2 else None
    ts = dt.datetime.fromtimestamp(last.t_ms / 1000, tz=dt.timezone.utc).replace(microsecond=0)
    return normalize_market_data(
        symbol=symbol,
        spot=last.close,
        timestamp_utc=ts,
        session=_session_et(now),
        source=source,
        high=last.high,
        low=last.low,
        prev_close=prev_close,
        volume=last.volume,
    )


class IBKRSnapshotProvider:
    """Callable snapshot provider for run_market_loop(snapshot_provider=...).

    Each call returns a MarketSnapshot only when a NEW bar is available, else
    None (the loop skips that cycle). IBKR requests are throttled to respect
    pacing limits. Fail-soft: any fetch error yields None, never an exception."""

    def __init__(self, symbol: str, *, source: str = "PAPER", bar_size: str = "1 min",
                 duration: str = "1 D", refetch_sec: float = 20.0,
                 fetch_fn: Optional[Callable] = None, clock: Callable[[], float] = time.time):
        self.symbol = symbol
        self.source = source
        self.bar_size = bar_size
        self.duration = duration
        self.refetch_sec = refetch_sec
        self._fetch_fn = fetch_fn
        self._clock = clock
        self._last_t_ms: Optional[int] = None
        self._last_fetch: float = 0.0

    def _fetch(self) -> List:
        if self._fetch_fn is not None:
            return self._fetch_fn(self.symbol, duration=self.duration, bar_size=self.bar_size)
        # Lazy import: pulls ibapi only at runtime, keeping this module CI-safe.
        from market.market_data_ibkr_history import fetch_bars
        return fetch_bars(self.symbol, duration=self.duration, bar_size=self.bar_size)

    def __call__(self, symbol: Optional[str] = None) -> Optional[MarketSnapshot]:
        now = self._clock()
        if (now - self._last_fetch) < self.refetch_sec:
            return None
        self._last_fetch = now
        try:
            bars = self._fetch()
        except Exception as e:  # never propagate into the loop
            print(f"[IBKR-LIVE] fetch error: {e}")
            return None
        if not bars:
            return None
        if bars[-1].t_ms == self._last_t_ms:
            return None  # no new bar since last emit
        self._last_t_ms = bars[-1].t_ms
        return snapshot_from_bars(self.symbol, bars, source=self.source)

    def warmup_snapshots(self) -> List[MarketSnapshot]:
        """Session bars so far -> ordered snapshots to pre-warm the indicators.

        Returns one snapshot per bar EXCEPT the most recent: the live loop emits
        the latest bar (and everything after) on its first call, so leaving it
        out avoids double-counting. Fail-soft: [] on any error. A 0DTE session
        engine must warm from the session's own history, not 35 minutes of
        real-time bars after every (re)start."""
        try:
            bars = self._fetch()
        except Exception as e:  # never propagate into startup
            print(f"[IBKR-LIVE] warmup fetch error: {e}")
            return []
        out: List[MarketSnapshot] = []
        for i in range(len(bars) - 1):
            snap = snapshot_from_bars(self.symbol, bars[: i + 1], source=self.source)
            if snap is not None:
                out.append(snap)
        return out

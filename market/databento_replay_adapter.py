#
# databento_replay_adapter.py
#
# Databento → MarketSnapshot Replay Adapter
# PHASE 17.a — SUBSTEP (EXPLICITLY AUTHORIZED)
#
# Responsible for:
# - Translating Databento historical events into MarketSnapshot objects
# - Preserving exact event ordering and timestamps
# - Feeding ReplayEngine with canonical, event-driven snapshots
#
# Explicitly NOT responsible for:
# - Strategy logic
# - Risk decisions
# - Exit decisions
# - Execution simulation
# - Aggregation or bar construction
#

from typing import Iterable, Iterator

import datetime as dt

from market_data import MarketSnapshot
from replay_engine import ReplayEngine


# ----------------------------
# Adapter
# ----------------------------

class DatabentoReplayAdapter:
    """
    Event-driven adapter that converts Databento historical
    events into canonical MarketSnapshot objects.

    This adapter is PURE TRANSLATION.
    """

    def __init__(
        self,
        *,
        symbol: str,
        source: str = "REPLAY",
    ):
        self.symbol = symbol
        self.source = source

    # ----------------------------
    # Public entrypoint
    # ----------------------------

    def snapshots_from_events(
        self,
        *,
        events: Iterable[dict],
    ) -> Iterator[MarketSnapshot]:
        """
        Convert Databento events into MarketSnapshot objects.

        Inputs:
            events: iterable of Databento-decoded event dicts.
                    Each event MUST contain:
                      - 'ts_event'   (nanoseconds since epoch or ISO timestamp)
                      - 'price'      (best available spot / trade price)

        Yields:
            MarketSnapshot (one per event)
        """

        for event in events:
            timestamp_utc = self._normalize_timestamp(event["ts_event"])
            spot = float(event["price"])

            yield MarketSnapshot(
                symbol=self.symbol,
                spot=spot,
                timestamp_utc=timestamp_utc,
                session=self._derive_session(timestamp_utc),
                source=self.source,
            )

    # ----------------------------
    # Helpers
    # ----------------------------

    @staticmethod
    def _normalize_timestamp(ts_event) -> dt.datetime:
        """
        Normalize Databento timestamps into naive UTC datetime.

        Supports:
        - nanoseconds since epoch (int)
        - ISO-8601 strings
        """

        if isinstance(ts_event, int):
            # Databento nanoseconds → seconds
            return dt.datetime.utcfromtimestamp(ts_event / 1_000_000_000)

        if isinstance(ts_event, str):
            # ISO string assumed UTC
            return dt.datetime.fromisoformat(ts_event.replace("Z", ""))

        raise RuntimeError("Unsupported Databento timestamp format")

    @staticmethod
    def _derive_session(timestamp_utc: dt.datetime) -> str:
        """
        Deterministically derive market session from UTC timestamp.

        US Equities / Options sessions:
        - PRE     : before 14:30 UTC
        - REGULAR : 14:30–21:00 UTC
        - POST    : after 21:00 UTC
        """

        t = timestamp_utc.time()

        if t < dt.time(14, 30):
            return "PRE"

        if dt.time(14, 30) <= t <= dt.time(21, 0):
            return "REGULAR"

        return "POST"


# ----------------------------
# Replay wiring helper
# ----------------------------

def run_databento_replay(
    *,
    replay_engine: ReplayEngine,
    events: Iterable[dict],
    symbol: str,
) -> None:
    """
    Convenience helper to run ReplayEngine
    directly from Databento events.

    This function does NOT add authority.
    """

    adapter = DatabentoReplayAdapter(symbol=symbol)
    snapshots = adapter.snapshots_from_events(events=events)

    replay_engine.run(snapshots)

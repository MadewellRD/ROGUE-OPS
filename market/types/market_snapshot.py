from dataclasses import dataclass
import datetime as dt


@dataclass(frozen=True)
class MarketSnapshot:
    snapshot_id: str
    timestamp_utc: dt.datetime
    session: str
    primary_symbol: str
    spot: float
    raw_primary: object

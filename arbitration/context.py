from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ArbitrationContext:
    snapshot_id: str
    session: str
    capital_snapshot: Dict
    open_positions: Dict

"""
Strategy Confidence Snapshot (Observability Only)
"""

from typing import Dict
import json
import datetime as dt
from governance.paths import data_dir, ensure_dir

CONFIDENCE_FILENAME = "strategy_confidence.jsonl"


def log_confidence_snapshot(
    *,
    snapshot_id: str,
    confidence: Dict[str, int],
) -> None:
    record = {
        "timestamp_utc": dt.datetime.utcnow().isoformat(),
        "snapshot_id": snapshot_id,
        "confidence": confidence,
    }

    log_path = ensure_dir(data_dir()) / CONFIDENCE_FILENAME
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")

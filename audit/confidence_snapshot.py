"""
Strategy Confidence Snapshot (Observability Only)
"""

from typing import Dict
import json
import datetime as dt
from pathlib import Path

CONFIDENCE_LOG_PATH = Path("/opt/rogueops/data/strategy_confidence.jsonl")


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

    CONFIDENCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIDENCE_LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")

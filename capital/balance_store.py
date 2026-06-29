#
# capital/balance_store.py
#
# Balance Store — Canonical Balance Cache (SQLite)
# PHASE 53 — BALANCE STORAGE AUTHORITY
#
# Responsibilities:
# - Persist latest AccountBalanceSnapshot per account
# - Enforce freshness window
# - Provide read-only access to consumers
#
# Explicitly NOT responsible for:
# - Fetching balances
# - Broker IO
# - Execution
# - Sizing
#

import sqlite3
import json
import time

from capital.account_balance_authority import AccountBalanceSnapshot
from governance.paths import ops_home


# ==================================================
# Storage config — on the shared ops volume (ROGUE_OPS_HOME) so the loop's
# balance writer and the console's reader share it and it survives recreates.
# ==================================================

_DB_PATH = ops_home() / "balance_store.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ==================================================
# DB init
# ==================================================

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS balances (
            account_id TEXT PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            written_ts REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


# ==================================================
# Store API
# ==================================================

def write_snapshot(snapshot: AccountBalanceSnapshot) -> None:
    """
    Persist latest balance snapshot for an account.

    Single-writer semantics enforced by PRIMARY KEY.
    """

    payload = {
        "account_id": snapshot.account_id,
        "currency": snapshot.currency,
        "net_liquidation": snapshot.net_liquidation,
        "available_funds": snapshot.available_funds,
        "excess_liquidity": snapshot.excess_liquidity,
        "buying_power": snapshot.buying_power,
        "timestamp_utc": snapshot.timestamp_utc,
        "source": snapshot.source,
        "snapshot_hash": snapshot.snapshot_hash,
    }

    conn = _get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO balances
        (account_id, snapshot_json, written_ts)
        VALUES (?, ?, ?)
        """,
        (
            snapshot.account_id,
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


def get_snapshot(
    *,
    account_id: str,
    max_age_seconds: int,
) -> AccountBalanceSnapshot:
    """
    Retrieve a cached balance snapshot.

    Fail-closed if:
    - Snapshot missing
    - Snapshot stale
    """

    conn = _get_conn()
    cur = conn.execute(
        """
        SELECT snapshot_json, written_ts
        FROM balances
        WHERE account_id = ?
        """,
        (account_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise RuntimeError("BALANCE_STORE_EMPTY")

    snapshot_json, written_ts = row
    age = time.time() - written_ts

    if age > max_age_seconds:
        raise RuntimeError(
            f"BALANCE_SNAPSHOT_STALE: age={int(age)}s>{max_age_seconds}s"
        )

    data = json.loads(snapshot_json)

    return AccountBalanceSnapshot(
        account_id=data["account_id"],
        currency=data["currency"],
        net_liquidation=float(data["net_liquidation"]),
        available_funds=float(data["available_funds"]),
        excess_liquidity=float(data["excess_liquidity"]),
        buying_power=float(data["buying_power"]),
        timestamp_utc=data["timestamp_utc"],
        source=data["source"],
        snapshot_hash=data["snapshot_hash"],
    )

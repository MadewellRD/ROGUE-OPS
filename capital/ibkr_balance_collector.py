#
# ibkr_balance_collector.py
#
# IBKR Balance Collector
# PHASE 53 — BROKER BALANCE INGESTION
#

import datetime as dt
import hashlib
import json

from broker.ibkr_runtime import get_ibkr_runtime
from capital.account_balance_authority import AccountBalanceSnapshot
from capital.balance_store import write_snapshot
from governance.kill_switch import kill_active, kill_context


_REQUIRED_TAGS = {
    "NetLiquidation",
    "AvailableFunds",
    "ExcessLiquidity",
    "BuyingPower",
}


def collect_ibkr_balance(
    *,
    account_id: str,
    execution_mode: str,
) -> AccountBalanceSnapshot:
    """
    Collect a live balance snapshot from IBKR.
    """

    if kill_active():
        ctx = kill_context()
        raise RuntimeError(
            f"BALANCE_COLLECTION_BLOCKED_BY_KILL:"
            f"{ctx.get('reason')}@{ctx.get('timestamp_utc')}"
        )

    if execution_mode not in ("PAPER", "CAPITAL"):
        raise RuntimeError(f"INVALID_EXECUTION_MODE:{execution_mode}")

    runtime = get_ibkr_runtime()

    try:
        values, currency = runtime.get_account_summary_blocking()
    except Exception as e:
        raise RuntimeError(f"IBKR_BALANCE_FETCH_FAILED:{str(e)}")

    missing = _REQUIRED_TAGS - values.keys()
    if missing:
        raise RuntimeError(f"BALANCE_FIELDS_MISSING:{sorted(missing)}")

    payload = {
        "account_id": account_id,
        "currency": currency,
        "net_liquidation": float(values["NetLiquidation"]),
        "available_funds": float(values["AvailableFunds"]),
        "excess_liquidity": float(values["ExcessLiquidity"]),
        "buying_power": float(values["BuyingPower"]),
        "source": execution_mode,
    }

    ts = (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    snapshot_hash = hashlib.sha256(encoded).hexdigest()

    snapshot = AccountBalanceSnapshot(
        account_id=account_id,
        currency=payload["currency"],
        net_liquidation=payload["net_liquidation"],
        available_funds=payload["available_funds"],
        excess_liquidity=payload["excess_liquidity"],
        buying_power=payload["buying_power"],
        timestamp_utc=ts,
        source=execution_mode,
        snapshot_hash=snapshot_hash,
    )

    write_snapshot(snapshot)
    return snapshot

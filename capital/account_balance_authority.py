#
# capital/account_balance_authority.py
#
# Account Balance Authority — Read-Only Capital Context
# PHASE 47 + PHASE 53 — BALANCE AWARENESS & CACHED ACCESS (NON-PERMISSIVE)
#
# Responsible for:
# - Producing deterministic account balance snapshots (producer path)
# - Serving cached balance snapshots to preflight / sizing (consumer path)
#
# Explicitly NOT responsible for:
# - Execution
# - Sizing math
# - Risk veto
# - Strategy logic
#
# This authority is:
# - Read-only
# - Fail-closed
# - Replay-safe
#

from dataclasses import dataclass
from typing import Literal, Optional
import datetime as dt
import hashlib
import json
import threading

from governance.kill_switch import kill_active, kill_context


# ==================================================
# Canonical Balance Snapshot
# ==================================================

@dataclass(frozen=True)
class AccountBalanceSnapshot:
    account_id: str
    currency: str

    net_liquidation: float
    available_funds: float
    excess_liquidity: float
    buying_power: float

    timestamp_utc: str
    source: Literal["SIM", "PAPER", "CAPITAL"]

    snapshot_hash: str


# ==================================================
# In-Process Cache (PHASE 53)
# ==================================================

_CACHED_SNAPSHOT: Optional[AccountBalanceSnapshot] = None
_CACHE_LOCK = threading.Lock()


# ==================================================
# Account Balance Authority
# ==================================================

class AccountBalanceAuthority:
    """
    Read-only authority producing and serving deterministic balance snapshots.
    """

    ENGINE_VERSION = "PHASE47_53_BALANCE_AUTHORITY_V2"

    # --------------------------------------------------
    # PRODUCER PATH (SIM only, deterministic)
    # --------------------------------------------------

    @staticmethod
    def snapshot(
        *,
        account_id: str,
        execution_mode: Literal["SIM", "PAPER", "CAPITAL"],
    ) -> AccountBalanceSnapshot:
        """
        Produce and cache a balance snapshot.

        This method is a PRODUCER.
        It MUST NOT be used by capital_preflight directly.
        """

        # --------------------------------------------------
        # Kill dominance
        # --------------------------------------------------

        if kill_active():
            ctx = kill_context()
            raise RuntimeError(
                f"KILL ACTIVE — balance snapshot blocked "
                f"(reason={ctx.get('reason')}, ts={ctx.get('timestamp_utc')})"
            )

        # --------------------------------------------------
        # SIM — fully deterministic, broker-isolated
        # --------------------------------------------------

        if execution_mode == "SIM":
            payload = {
                "account_id": account_id,
                "currency": "USD",
                "net_liquidation": 100_000.0,
                "available_funds": 100_000.0,
                "excess_liquidity": 100_000.0,
                "buying_power": 200_000.0,
                "source": "SIM",
            }

            ts = (
                dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
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

            snap = AccountBalanceSnapshot(
                account_id=account_id,
                currency=payload["currency"],
                net_liquidation=payload["net_liquidation"],
                available_funds=payload["available_funds"],
                excess_liquidity=payload["excess_liquidity"],
                buying_power=payload["buying_power"],
                timestamp_utc=ts,
                source="SIM",
                snapshot_hash=snapshot_hash,
            )

            with _CACHE_LOCK:
                global _CACHED_SNAPSHOT
                _CACHED_SNAPSHOT = snap

            return snap

        # --------------------------------------------------
        # PAPER / CAPITAL — forbidden here
        # --------------------------------------------------

        raise RuntimeError(
            "BROKER_BALANCE_COLLECTION_NOT_ALLOWED_IN_AUTHORITY "
            "(use external collector)"
        )

    # --------------------------------------------------
    # CONSUMER PATH (PHASE 53)
    # --------------------------------------------------

    @staticmethod
    def get_cached_snapshot(
        *,
        account_id: str,
        max_age_seconds: int,
    ) -> AccountBalanceSnapshot:
        """
        Retrieve a cached balance snapshot.

        This method:
        - Performs NO broker IO
        - Fails closed if snapshot missing, stale, or mismatched
        """

        with _CACHE_LOCK:
            snap = _CACHED_SNAPSHOT

        if snap is None:
            raise RuntimeError("BALANCE_CACHE_EMPTY")

        if snap.account_id != account_id:
            raise RuntimeError("BALANCE_ACCOUNT_MISMATCH")

        ts = dt.datetime.fromisoformat(
            snap.timestamp_utc.replace("Z", "+00:00")
        )
        age = (dt.datetime.now(dt.timezone.utc) - ts).total_seconds()

        if age > max_age_seconds:
            raise RuntimeError(
                f"BALANCE_SNAPSHOT_STALE:{int(age)}s>{max_age_seconds}s"
            )

        return snap

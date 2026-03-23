#
# capital_preflight.py
#
# Capital Preflight — Go / No-Go Authority
# PHASE 52 + PHASE 53 — CAPITAL ARMING & GOVERNANCE
#
# Purpose:
# - Perform final go/no-go checks before CAPITAL execution
# - Consume cached balance snapshot (NO broker IO)
# - Enforce explicit operator attestation and limits
#
# Explicitly NOT responsible for:
# - Fetching balances
# - Execution
# - Sizing
# - Strategy logic
#

import os
import datetime as dt
from typing import Dict, Any

from governance.kill_switch import kill_active, kill_context
from capital.balance_store import get_snapshot
from capital.account_balance_authority import AccountBalanceSnapshot


# ==================================================
# Helpers
# ==================================================

def _fail(reason: str):
    raise RuntimeError(f"CAPITAL PREFLIGHT FAILED: {reason}")


def _require_env(var: str) -> str:
    v = os.getenv(var)
    if not v:
        _fail(f"MISSING_ENV_VAR:{var}")
    return v


def _parse_bool(v: str) -> bool:
    return v.lower() in ("1", "true", "yes")


def _parse_utc(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


# ==================================================
# Preflight
# ==================================================

def run_capital_preflight() -> Dict[str, Any]:
    """
    Perform capital go/no-go preflight checks.

    This function:
    - MUST NOT perform broker IO
    - MUST consume cached balance snapshot
    - MUST fail closed
    """

    # --------------------------------------------------
    # Kill dominance
    # --------------------------------------------------

    if kill_active():
        ctx = kill_context()
        _fail(
            f"KILL_ACTIVE:{ctx.get('reason')}@{ctx.get('timestamp_utc')}"
        )

    # --------------------------------------------------
    # Required environment
    # --------------------------------------------------

    execution_mode = _require_env("EXECUTION_MODE")
    if execution_mode != "CAPITAL":
        _fail(f"INVALID_EXECUTION_MODE:{execution_mode}")

    ops_env = _require_env("OPS_ENV")
    if ops_env != "PROD":
        _fail(f"INVALID_OPS_ENV:{ops_env}")

    account_id = _require_env("IBKR_ACCOUNT_ID")

    # --------------------------------------------------
    # Explicit operator attestations
    # --------------------------------------------------

    go_no_go = _parse_bool(_require_env("OPS_GO_NO_GO_ATTESTED"))
    if not go_no_go:
        _fail("GO_NO_GO_NOT_ATTESTED")

    capital_armed = _parse_bool(_require_env("CAPITAL_ARMED"))
    if not capital_armed:
        _fail("CAPITAL_NOT_ARMED")

    last_kill_drill = _parse_utc(_require_env("OPS_LAST_KILL_DRILL_UTC"))

    now = dt.datetime.now(dt.timezone.utc)
    if (now - last_kill_drill).days > 7:
        _fail("KILL_DRILL_TOO_OLD")

    # --------------------------------------------------
    # Risk limits (static)
    # --------------------------------------------------

    max_daily_loss = float(_require_env("MAX_DAILY_LOSS_USD"))
    max_notional = float(_require_env("MAX_CAPITAL_NOTIONAL_USD"))
    max_contracts = int(_require_env("MAX_CAPITAL_CONTRACTS"))

    if max_daily_loss <= 0:
        _fail("INVALID_MAX_DAILY_LOSS")

    if max_notional <= 0:
        _fail("INVALID_MAX_NOTIONAL")

    if max_contracts <= 0:
        _fail("INVALID_MAX_CONTRACTS")

    # --------------------------------------------------
    # Balance snapshot (CONSUMER PATH ONLY)
    # --------------------------------------------------

    try:
        balance: AccountBalanceSnapshot = get_snapshot(
            account_id=account_id,
            max_age_seconds=60,
        )
    except Exception as e:
        _fail(f"BALANCE_SNAPSHOT_FAILED:{str(e)}")

    # --------------------------------------------------
    # Capital sanity checks
    # --------------------------------------------------

    if balance.net_liquidation <= 0:
        _fail("NET_LIQUIDATION_NON_POSITIVE")

    if balance.available_funds <= 0:
        _fail("AVAILABLE_FUNDS_NON_POSITIVE")

    if balance.source != "CAPITAL":
        _fail(f"INVALID_BALANCE_SOURCE:{balance.source}")

    # --------------------------------------------------
    # PASS
    # --------------------------------------------------

    return {
        "status": "CAPITAL_GO",
        "account_id": account_id,
        "net_liquidation": balance.net_liquidation,
        "available_funds": balance.available_funds,
        "buying_power": balance.buying_power,
        "balance_snapshot_hash": balance.snapshot_hash,
        "checked_utc": now.isoformat().replace("+00:00", "Z"),
    }

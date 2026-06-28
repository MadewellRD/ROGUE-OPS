#
# api/terminal_state.py
#
# Terminal State Aggregator
#
# Gathers a point-in-time view of ROGUE:OPS for the operator console:
# kill/ops state, capital, risk/daily-loss, the open position, the latest market
# frame, and the latest shadow read.
#
# CROSS-PROCESS: the trading loop and the console run as SEPARATE processes
# (separate containers). The loop holds the live frame / risk / position in its
# own memory, so it PUBLISHES a full snapshot to a shared file
# (ROGUE_OPS_HOME/state.json) each cycle. The console, which has no live
# in-process state, reads that file. Kill + arm are always re-resolved live
# (they are file-backed + cross-process) so safety state is never stale.
#
# Read-only for the console. Defensive. Never raises.
#

import os
import json
import time
import datetime as dt
from typing import Any, Dict, Optional

# Live state held by the LOOP process (transient, in-memory).
_LAST_FRAME: Dict[str, Any] = {}
_LAST_SHADOW: Dict[str, Any] = {}

# How fresh the loop's published snapshot must be for the console to trust it.
_STATE_FILE_MAX_AGE_SEC = 90.0


def _now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ==================================================
# Loop-side publishing
# ==================================================

def publish_frame(*, snapshot=None, indicators=None, signal_status: Optional[str] = None) -> None:
    """Called by the market loop each cycle to surface live market state."""
    global _LAST_FRAME
    frame: Dict[str, Any] = {"ts_utc": _now()}
    if snapshot is not None:
        frame["symbol"] = getattr(snapshot, "symbol", None)
        frame["spot"] = getattr(snapshot, "spot", None)
        frame["session"] = getattr(snapshot, "session", None)
        frame["source"] = getattr(snapshot, "source", None)
    if indicators is not None:
        req = dict(getattr(indicators, "required", {}) or {})
        adv = dict(getattr(indicators, "advisory", {}) or {})
        frame["indicators"] = req
        frame["vwap"] = adv.get("VWAP")
        frame["required_passed"] = getattr(indicators, "required_passed", None)
    if signal_status is not None:
        frame["signal_status"] = signal_status
    _LAST_FRAME = frame
    publish_state_file()


def get_last_frame() -> Dict[str, Any]:
    """The most recent market frame published by the live loop (or {})."""
    return dict(_LAST_FRAME)


def publish_shadow(read: Dict[str, Any]) -> None:
    """Called by the shadow runner when an auto read completes (advisory only)."""
    global _LAST_SHADOW
    r = dict(read or {})
    r["ts_utc"] = _now()
    _LAST_SHADOW = r
    publish_state_file()


# ==================================================
# Helpers
# ==================================================

def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # pragma: no cover - terminal must not crash
        return {"error": str(e)} if default is None else default


def _live_kill() -> Dict[str, Any]:
    from governance.kill_switch import kill_context
    return kill_context()


def _live_arm() -> Dict[str, Any]:
    from api.control import arm_state
    return {"armed": arm_state()}


# ==================================================
# Full state snapshot (built from THIS process)
# ==================================================

def build_state() -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "ts_utc": _now(),
        "system": "ROGUE:OPS",
        "mode": os.getenv("EXECUTION_MODE", "SIM"),
        "ops_env": os.getenv("OPS_ENV", ""),
        "ops_mode": os.getenv("OPS_MODE", ""),
    }

    state["kill"] = _safe(_live_kill)

    def _risk():
        from capital.daily_loss_governor import current_realized_pnl, is_breached, _max_loss
        return {
            "realized_pnl_usd": current_realized_pnl(),
            "max_daily_loss_usd": _max_loss(),
            "breached": is_breached(),
        }
    state["risk"] = _safe(_risk)

    def _capital():
        try:
            from capital.balance_store import get_snapshot
            account = os.getenv("ROGUE_BALANCE_ACCOUNT", "IBKR")
            snap = get_snapshot(account_id=account, max_age_seconds=86400)
        except Exception:
            return None
        if snap is None:
            return None
        return {
            "net_liquidation": getattr(snap, "net_liquidation", None),
            "available_funds": getattr(snap, "available_funds", None),
            "excess_liquidity": getattr(snap, "excess_liquidity", None),
            "buying_power": getattr(snap, "buying_power", None),
            "currency": getattr(snap, "currency", None),
            "as_of": getattr(snap, "timestamp_utc", None),
        }
    state["capital"] = _capital()

    def _position():
        from execution.position_store import get_position_store
        ps = get_position_store()
        if not ps.has_open_position():
            return None
        p = ps.get_open_position()
        return {
            "symbol": getattr(p, "symbol", None),
            "right": getattr(p, "right", None),
            "strike": getattr(p, "strike", None),
            "expiry": getattr(p, "expiry", None),
            "action": getattr(p, "action", None),
            "quantity": getattr(p, "quantity", None),
            "entry_price": getattr(p, "entry_price", None),
            "opened_at_utc": str(getattr(p, "opened_at_utc", "")),
        }
    state["position"] = _safe(_position)

    state["market"] = _LAST_FRAME or None

    state["brokers"] = {
        "options": os.getenv("BROKER", "IBKR") if os.getenv("BROKER") else "IBKR",
        "equities": os.getenv("EQUITY_BROKER", "ROBINHOOD"),
    }

    state["control"] = _safe(_live_arm, {"armed": False})
    state["shadow"] = _LAST_SHADOW or None
    return state


# ==================================================
# Shared-file bridge (loop writes, console reads)
# ==================================================

def _state_file_path():
    from governance.paths import ops_home
    return ops_home() / "state.json"


def publish_state_file() -> None:
    """LOOP side: write the full live snapshot to the shared volume so a separate
    console process can render it. Best-effort; never raises into the loop."""
    try:
        snap = build_state()
        snap["published_ts"] = _now()
        p = _state_file_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, default=str), encoding="utf-8")
    except Exception:
        pass


def _read_state_file(max_age_sec: float = _STATE_FILE_MAX_AGE_SEC) -> Optional[Dict[str, Any]]:
    try:
        p = _state_file_path()
        if not p.exists():
            return None
        age = time.time() - p.stat().st_mtime
        if age > max_age_sec:
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        data["_age_sec"] = round(age, 1)
        return data
    except Exception:
        return None


def get_terminal_state() -> Dict[str, Any]:
    """CONSOLE side: prefer a fresh loop-published snapshot (this process has no
    live frame/risk/position of its own). Kill + control are always re-resolved
    live so safety state is never stale."""
    snap = _read_state_file()
    if snap is not None:
        snap["source"] = "loop"
        snap["ts_utc"] = _now()
        snap["kill"] = _safe(_live_kill)
        snap["control"] = _safe(_live_arm, {"armed": False})
        return snap
    s = build_state()
    s["source"] = "local"
    return s

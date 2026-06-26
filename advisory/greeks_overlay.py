# greeks_overlay.py
#
# Greeks / IV Overlay — Read-Only Telemetry
# PHASE 43 — GREEKS & IV OVERLAY (NON-AUTHORITATIVE)
#
# Responsible for:
# - Fetching option microstructure metrics
# - Normalizing Greeks and liquidity data
# - Emitting immutable advisory snapshots
#
# Explicitly NOT responsible for:
# - Signal gating
# - Entry / exit decisions
# - Risk sizing
# - Execution routing
# - State transitions
#
# This module MUST NEVER be imported by:
# - execution_router.py
# - state_machine.py
# - risk_engine.py
# - signal_engine.py
#

from dataclasses import dataclass
from typing import Optional
import datetime as dt


# ==================================================
# Greeks Snapshot (IMMUTABLE, ADVISORY ONLY)
# ==================================================

@dataclass(frozen=True)
class GreeksSnapshot:
    symbol: str
    expiry: str
    strike: float
    right: str                 # "C" or "P"
    timestamp_utc: str

    delta: float
    gamma: float
    theta: float
    iv: float
    iv_change: float

    volume: int
    open_interest: int
    spread_pct: float
    premium: float

    # Derived (read-only)
    gamma_efficiency: float    # gamma / premium
    vol_oi_ratio: float        # volume / max(open_interest, 1)


# ==================================================
# Greeks Overlay Engine
# ==================================================

class GreeksOverlayEngine:
    """
    Read-only Greeks overlay engine.

    Produces optional advisory snapshots.
    If ANY required field is missing or invalid → returns None.
    """

    ENGINE_VERSION = "PHASE43_GREEKS_V1"

    @staticmethod
    def fetch_snapshot(
        *,
        symbol: str,
        expiry: str,
        strike: float,
        right: str,
        timestamp_utc: str,
    ) -> Optional[GreeksSnapshot]:
        """
        Fetch and normalize Greeks snapshot.

        FAIL-CLOSED RULE:
        - Any missing / invalid metric → return None
        """

        try:
            # --------------------------------------------------
            # NOTE:
            # Replace the stub below with SteadyAPI / worker feed
            # This is intentionally isolated and non-authoritative
            # --------------------------------------------------

            # ---- STUB PLACEHOLDER (EXPECTED TO BE REPLACED) ----
            # These values MUST come from live option data
            delta = 0.45
            gamma = 0.012
            theta = -0.08
            iv = 0.32
            iv_change = 0.04

            volume = 1200
            open_interest = 800
            spread_pct = 0.06
            premium = 2.40
            # --------------------------------------------------

            if premium <= 0 or gamma <= 0:
                return None

            gamma_efficiency = gamma / premium
            vol_oi_ratio = volume / max(open_interest, 1)

            return GreeksSnapshot(
                symbol=symbol,
                expiry=expiry,
                strike=strike,
                right=right,
                timestamp_utc=timestamp_utc,

                delta=delta,
                gamma=gamma,
                theta=theta,
                iv=iv,
                iv_change=iv_change,

                volume=volume,
                open_interest=open_interest,
                spread_pct=spread_pct,
                premium=premium,

                gamma_efficiency=gamma_efficiency,
                vol_oi_ratio=vol_oi_ratio,
            )

        except Exception:
            return None


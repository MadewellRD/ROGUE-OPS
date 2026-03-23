#
# confidence_engine.py
#
# Confidence Engine — Read-Only Advisory Metadata
# PHASE 42 — CONFIDENCE ENGINE (NON-AUTHORITATIVE)
#
# This module remains PURELY OBSERVATIONAL.
# It MUST NOT influence execution, authorization, or risk.
#

from dataclasses import dataclass
from typing import Dict, Any, Optional

from signal_context import SignalContext
from indicator_authority import IndicatorAssertion


# ==================================================
# Confidence Report (Metadata Only)
# ==================================================

@dataclass(frozen=True)
class ConfidenceReport:
    """
    Non-binding, advisory confidence metadata.

    This object:
    - Carries NO authority
    - Is NOT hashed
    - Is NOT consumed by execution logic
    - May be fully suppressed without consequence
    """

    symbol: str
    timestamp_utc: str

    confidence_label: str              # "A+", "B", "C", or "UNAVAILABLE"
    confidence_score: Optional[float]  # 0.0 – 1.0 or None

    rationale: Dict[str, Any]

    engine_version: str


# ==================================================
# Internal helpers (PURE)
# ==================================================

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(v, hi))


def _safe_div(n: float, d: float) -> Optional[float]:
    if d == 0:
        return None
    return n / d


# ==================================================
# Confidence Engine
# ==================================================

class ConfidenceEngine:
    """
    Read-only confidence engine.

    Observes:
    - SignalContext
    - IndicatorAssertion
    - OPTIONAL Greeks snapshot (passed via context metadata)

    Produces:
    - Advisory confidence metadata ONLY
    """

    ENGINE_VERSION = "PHASE42_CONFIDENCE_V2"

    @staticmethod
    def evaluate(
        *,
        signal_context: SignalContext,
        indicator_assertion: IndicatorAssertion,
        greeks_snapshot: Optional[Dict[str, Any]] = None,
    ) -> ConfidenceReport:
        """
        Generate advisory confidence metadata.

        FAIL-CLOSED RULE:
        - If Greeks are missing or incomplete → confidence_score = None
        - Execution behavior MUST remain identical
        """

        rationale: Dict[str, Any] = {
            "advisory_only": True,
            "required_indicators_passed": indicator_assertion.required_passed,
        }

        # --------------------------------------------------
        # Default posture
        # --------------------------------------------------

        confidence_score: Optional[float] = None
        confidence_label = "UNAVAILABLE"

        # --------------------------------------------------
        # Greeks-based confidence (OPTIONAL)
        # --------------------------------------------------

        if greeks_snapshot:
            try:
                gamma = greeks_snapshot["gamma"]
                iv_delta = greeks_snapshot["iv_delta"]
                vol_oi = greeks_snapshot["vol_oi_ratio"]
                spread_pct = greeks_snapshot["spread_pct"]
                premium = greeks_snapshot["premium"]

                # Normalizations (bounded, deterministic)
                gamma_norm = _clamp(_safe_div(gamma, greeks_snapshot.get("max_gamma", 1.0)) or 0.0)
                iv_norm = _clamp(abs(iv_delta) / greeks_snapshot.get("max_iv_delta", 1.0))
                vol_oi_norm = _clamp(min(vol_oi / 2.0, 1.0))
                liquidity_norm = _clamp(1.0 - spread_pct)

                gamma_eff = _safe_div(gamma, premium)
                if gamma_eff is None:
                    raise ValueError("Invalid gamma efficiency")

                gamma_eff_norm = _clamp(gamma_eff)

                # Weighted Edge Score
                confidence_score = _clamp(
                    0.25 * gamma_norm +
                    0.20 * iv_norm +
                    0.15 * vol_oi_norm +
                    0.15 * liquidity_norm +
                    0.25 * gamma_eff_norm
                )

                # Label mapping (NON-AUTHORITATIVE)
                if confidence_score >= 0.80:
                    confidence_label = "A+"
                elif confidence_score >= 0.60:
                    confidence_label = "B"
                else:
                    confidence_label = "C"

                rationale.update({
                    "gamma_norm": gamma_norm,
                    "iv_norm": iv_norm,
                    "vol_oi_norm": vol_oi_norm,
                    "liquidity_norm": liquidity_norm,
                    "gamma_eff_norm": gamma_eff_norm,
                })

            except Exception as e:
                rationale["confidence_error"] = str(e)
                confidence_score = None
                confidence_label = "UNAVAILABLE"

        return ConfidenceReport(
            symbol=signal_context.symbol,
            timestamp_utc=signal_context.timestamp_utc,
            confidence_label=confidence_label,
            confidence_score=confidence_score,
            rationale=rationale,
            engine_version=ConfidenceEngine.ENGINE_VERSION,
        )

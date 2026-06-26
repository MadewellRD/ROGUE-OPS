#
# promotion_registry.py
#
# CAPITAL Promotion Registry
# PHASE 46 — PROMOTION AUTHORITY
#
# Purpose:
# - Provide a single source of truth for CAPITAL promotion
# - Fail-closed if promotion is missing or invalid
#
# This module is intentionally SIMPLE.
# Complexity lives in enforcement, not storage.
#

import json
import os
from typing import Dict, Any

from execution.execution_envelope import ExecutionEnvelope


# ==================================================
# Promotion source
# ==================================================
# For v1.0.0 this is file-based.
# Future versions may use Firestore or signed artifacts.
# ==================================================

PROMOTION_FILE = os.getenv("OPS_PROMOTION_FILE")


# ==================================================
# Load active promotion
# ==================================================

def load_active_promotion() -> Dict[str, Any] | None:
    """
    Load the active promotion artifact.

    Returns:
        promotion dict if present, else None
    """

    if not PROMOTION_FILE:
        return None

    if not os.path.exists(PROMOTION_FILE):
        return None

    with open(PROMOTION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================================================
# Promotion validation
# ==================================================

def validate_promotion_for_envelope(
    promotion: Dict[str, Any],
    envelope: ExecutionEnvelope,
) -> None:
    """
    Validate that the promotion authorizes this envelope.

    Raises RuntimeError on any violation.
    """

    # --------------------------------------------------
    # Execution mode
    # --------------------------------------------------

    if promotion.get("allowed_execution_mode") != "CAPITAL":
        raise RuntimeError("PROMOTION_NOT_FOR_CAPITAL")

    # --------------------------------------------------
    # Expiry
    # --------------------------------------------------

    if envelope.created_utc >= promotion.get("expires_utc", ""):
        raise RuntimeError("PROMOTION_EXPIRED")

    # --------------------------------------------------
    # Symbol scope
    # --------------------------------------------------

    symbol_scope = promotion.get("symbol_scope", [])
    if envelope.intent.symbol not in symbol_scope:
        raise RuntimeError("SYMBOL_NOT_IN_PROMOTION_SCOPE")

    # --------------------------------------------------
    # Contract limits
    # --------------------------------------------------

    max_contracts = promotion.get("max_contracts")
    if max_contracts is not None:
        if envelope.intent.quantity > max_contracts:
            raise RuntimeError("PROMOTION_CONTRACT_LIMIT_EXCEEDED")

    # --------------------------------------------------
    # Version binding
    # --------------------------------------------------

    if promotion.get("engine_version") != envelope.engine_version:
        raise RuntimeError("ENGINE_VERSION_MISMATCH")

    if promotion.get("law_version_hash") != envelope.law_version_hash:
        raise RuntimeError("LAW_VERSION_MISMATCH")

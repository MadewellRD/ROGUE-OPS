#
# ops_config.py
#
# OPS Configuration & Deployment Hardening
# PHASE 19 + PHASE 7.4 — ATOMIC
#
# Responsible for:
# - Defining immutable runtime configuration
# - Environment identity (LIVE / PAPER / REPLAY / SIM)
# - Version and build stamping
# - Preventing silent configuration drift
# - HARD gating LIVE execution
#
# Explicitly NOT responsible for:
# - Secrets loading
# - Feature flags
# - Strategy parameters
#

import os
import hashlib
from dataclasses import dataclass
from typing import Literal


# ----------------------------
# OPS Modes
# ----------------------------

OPSMode = Literal["LIVE", "PAPER", "REPLAY", "SIM"]


# ----------------------------
# Configuration Schema
# ----------------------------

@dataclass(frozen=True)
class OPSConfig:
    """
    Immutable OPS runtime configuration.
    """

    mode: OPSMode
    environment: str
    version: str
    build_hash: str

    # Execution authorization (derived, not configurable)
    live_execution_allowed: bool
    paper_execution_allowed: bool


# ----------------------------
# Helpers
# ----------------------------

def _compute_build_hash() -> str:
    """
    Compute a coarse build hash from environment variables.

    This is NOT cryptographic signing.
    It is drift detection.
    """
    material = "|".join(
        [
            os.getenv("OPS_MODE", ""),
            os.getenv("OPS_ENV", ""),
            os.getenv("OPS_VERSION", ""),
            os.getenv("EXECUTION_MODE", ""),
        ]
    ).encode("utf-8")

    return hashlib.sha256(material).hexdigest()


# ----------------------------
# Loader (Fail-Fast)
# ----------------------------

def load_ops_config() -> OPSConfig:
    """
    Load and validate OPS configuration.

    This function MUST be called at process start.
    """

    mode = os.getenv("OPS_MODE")
    env = os.getenv("OPS_ENV")
    version = os.getenv("OPS_VERSION")
    execution_mode = os.getenv("EXECUTION_MODE", "SIM")

    # ----------------------------
    # BASIC VALIDATION
    # ----------------------------

    if mode not in ("LIVE", "PAPER", "REPLAY", "SIM"):
        raise RuntimeError("Invalid or missing OPS_MODE")

    if not env:
        raise RuntimeError("OPS_ENV not set")

    if not version:
        raise RuntimeError("OPS_VERSION not set")

    if execution_mode not in ("SIM", "PAPER", "LIVE", "CAPITAL"):
        raise RuntimeError("Invalid EXECUTION_MODE")

    # ----------------------------
    # HARD EXECUTION GATES
    # ----------------------------

    # LIVE execution is NEVER implicit
    live_execution_allowed = False
    paper_execution_allowed = False

    if mode == "LIVE":
        if execution_mode != "LIVE":
            raise RuntimeError(
                "OPS_MODE=LIVE requires EXECUTION_MODE=LIVE"
            )

        if env != "PROD":
            raise RuntimeError(
                "LIVE execution is only permitted in OPS_ENV=PROD"
            )

        live_execution_allowed = True

    if mode == "PAPER":
        if execution_mode not in ("PAPER", "SIM"):
            raise RuntimeError(
                "OPS_MODE=PAPER requires EXECUTION_MODE=PAPER or SIM"
            )

        paper_execution_allowed = True

    if mode in ("SIM", "REPLAY"):
        if execution_mode != "SIM":
            raise RuntimeError(
                f"OPS_MODE={mode} requires EXECUTION_MODE=SIM"
            )

    # ----------------------------
    # FINAL CONFIG
    # ----------------------------

    return OPSConfig(
        mode=mode,  # type: ignore
        environment=env,
        version=version,
        build_hash=_compute_build_hash(),
        live_execution_allowed=live_execution_allowed,
        paper_execution_allowed=paper_execution_allowed,
    )

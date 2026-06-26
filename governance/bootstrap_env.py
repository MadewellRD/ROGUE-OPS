#
# bootstrap_env.py
#
# Environment Bootstrap Authority
# PHASE 54 — ENVIRONMENT HYDRATION (NON-REGRESSIVE)
#
# Responsibilities:
# - Load required OPS environment variables from JSON
# - Populate os.environ ONLY if missing
# - Fail fast if required values cannot be resolved
#
# Explicitly NOT responsible for:
# - Capital checks
# - Broker IO
# - Secrets validation
# - OPS mode decisions
#

import os
import json
from pathlib import Path


# ==================================================
# CONFIG
# ==================================================

# JSON file containing environment defaults (cross-platform path)
from governance.paths import bootstrap_path

# Keys required only when running a broker/cloud-backed mode.
# SIM and REPLAY are fully self-contained and require none of these.
_CLOUD_REQUIRED_KEYS = [
    "IBKR_ACCOUNT_ID",
    "GCP_PROJECT_ID",
    "DOCTRINE_BUCKET",
    "GOOGLE_APPLICATION_CREDENTIALS",
]


def _required_keys() -> list:
    execution_mode = os.getenv("EXECUTION_MODE", "SIM")
    ops_mode = os.getenv("OPS_MODE", "")
    sim_like = execution_mode == "SIM" or ops_mode in ("SIM", "REPLAY")
    return [] if sim_like else _CLOUD_REQUIRED_KEYS


# ==================================================
# BOOTSTRAP
# ==================================================

def bootstrap_environment() -> None:
    """
    Populate required environment variables from JSON
    WITHOUT overriding shell-provided values.

    Fail fast if any required variable remains unresolved.
    """

    data = {}

    path = bootstrap_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            raise RuntimeError(
                f"BOOTSTRAP_JSON_INVALID:{path}:{e}"
            )

    missing = []

    for key in _required_keys():
        if os.getenv(key):
            continue

        if key in data:
            os.environ[key] = str(data[key])
        else:
            missing.append(key)

    if missing:
        raise RuntimeError(
            f"BOOTSTRAP_ENV_INCOMPLETE:missing={missing}"
        )

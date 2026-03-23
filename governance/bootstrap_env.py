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

# JSON file containing environment defaults
BOOTSTRAP_PATH = Path(
    os.getenv(
        "ROGUE_BOOTSTRAP_JSON",
        "/opt/rogueops/rogue-ops-bootstrap.json",
    )
)

REQUIRED_KEYS = [
    "IBKR_ACCOUNT_ID",
    "GCP_PROJECT_ID",
    "DOCTRINE_BUCKET",
    "GOOGLE_APPLICATION_CREDENTIALS",
]


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

    if BOOTSTRAP_PATH.exists():
        try:
            data = json.loads(BOOTSTRAP_PATH.read_text())
        except Exception as e:
            raise RuntimeError(
                f"BOOTSTRAP_JSON_INVALID:{BOOTSTRAP_PATH}:{e}"
            )

    missing = []

    for key in REQUIRED_KEYS:
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

#
# run_sim_regression.py
#
# PHASE 49 — SIM REGRESSION HARNESS (AUTHORITATIVE)
#
# Purpose:
# - Execute SIM trade driver
# - Capture invariant outputs
# - Compare against golden record
# - FAIL HARD on any semantic deviation
#
# Volatile values (hashes, timestamps) are OBSERVED but NOT compared.
#

import json
import os
import subprocess
import sys
import re
from pathlib import Path


# ==================================================
# Configuration
# ==================================================

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "sim_golden" / "sim_phase48_golden.json"

# Run the SIM driver as a module from the repo root using the SAME
# interpreter. Works identically on Windows, macOS, and Linux
# (the old ["python3", "sim_trade_driver.py"] was broken on both
# counts: wrong path and a Unix-only interpreter name).
SIM_CMD = [sys.executable, "-m", "execution.sim_trade_driver"]

# Deterministic SIM environment for the child process.
SIM_ENV = {
    "OPS_MODE": "SIM",
    "OPS_ENV": "DEV",
    "OPS_VERSION": "0.0.0-sim",
    "EXECUTION_MODE": "SIM",
}


# ==================================================
# Helpers
# ==================================================

def extract(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    if not m:
        raise RuntimeError(f"Failed to extract pattern: {pattern}")
    return m.group(1)


# ==================================================
# Main
# ==================================================

def main() -> None:
    if not GOLDEN_PATH.exists():
        raise RuntimeError("Golden record missing")

    golden = json.loads(GOLDEN_PATH.read_text())

    proc = subprocess.run(
        SIM_CMD,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
        env={**os.environ, **SIM_ENV},
    )

    stdout = proc.stdout

    if proc.returncode != 0:
        print(stdout)
        print(proc.stderr)
        raise RuntimeError("SIM execution failed")

    # --------------------------------------------------
    # Observed (volatile + invariant)
    # --------------------------------------------------

    observed = {
        "indicator_assertion_hash": extract(
            r"\[ASSERTION HASH\] ([a-f0-9]{64})", stdout
        ),
        "envelope_hash": extract(
            r"\[SIM ENVELOPE\] ([a-f0-9]{64})", stdout
        ),
        "parity_hash": extract(
            r"\[PARITY HASH\] ([a-f0-9]{64})", stdout
        ),
        "execution_status": extract(
            r"\[SIM RESULT\] (\w+)", stdout
        ),
    }

    # --------------------------------------------------
    # Invariant comparisons ONLY
    # --------------------------------------------------

    mismatches = []

    if observed["indicator_assertion_hash"] != golden["indicator_assertion_hash"]:
        mismatches.append("indicator_assertion_hash")

    if observed["execution_status"] != golden["execution"]["status"]:
        mismatches.append("execution.status")

    # --------------------------------------------------
    # Final verdict
    # --------------------------------------------------

    if mismatches:
        raise RuntimeError(
            f"SIM REGRESSION DETECTED — mismatched invariants: {mismatches}"
        )

    print("SIM REGRESSION PASS — invariants intact")
    print(f"Observed envelope_hash (volatile): {observed['envelope_hash']}")
    print(f"Observed parity_hash   (volatile): {observed['parity_hash']}")


# ==================================================
# Entrypoint
# ==================================================

if __name__ == "__main__":
    main()

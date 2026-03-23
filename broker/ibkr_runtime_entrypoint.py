# broker/ibkr_runtime_entrypoint.py
#
# IBKR Runtime Entrypoint
# Systemd-managed, long-lived broker access plane
#
# NON-NEGOTIABLE:
# - No strategy logic
# - No capital logic
# - No execution decisions
#

import os
import sys
import time

# --- HARD REQUIREMENT ---
# Ensure project root is on sys.path
PROJECT_ROOT = "/opt/rogueops"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from broker.ibkr_runtime import IBKRRuntime


def main():
    host = os.environ.get("IBKR_HOST")
    port = int(os.environ.get("IBKR_PORT", "7497"))

    if not host:
        raise RuntimeError("IBKR_HOST not set")

    runtime = IBKRRuntime(host=host, port=port)

    # Block forever; systemd owns lifecycle
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()

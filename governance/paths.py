#
# paths.py
#
# OPS Filesystem Path Authority (CROSS-PLATFORM)
#
# Single source of truth for where ROGUE:OPS reads and writes
# runtime state (audit logs, data, bootstrap config).
#
# Historically these paths were hardcoded to "/opt/rogueops",
# which is invalid on Windows dev boxes. This module resolves a
# single configurable home directory with an OS-appropriate
# default, so the same code runs on Linux, macOS, and Windows.
#
# Resolution order for the OPS home directory:
#   1. $ROGUE_OPS_HOME           (explicit override, all platforms)
#   2. Windows  -> %LOCALAPPDATA%\rogueops  (fallback: ~\rogueops)
#   3. POSIX    -> /opt/rogueops            (preserves prod layout)
#
# All helpers resolve LAZILY (read env at call time) so that an
# override set after import is still honoured.
#

import os
from pathlib import Path


def ops_home() -> Path:
    """Resolve the OPS runtime home directory (not auto-created)."""
    override = os.getenv("ROGUE_OPS_HOME")
    if override:
        return Path(override)

    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "rogueops"

    return Path("/opt/rogueops")


def audit_dir() -> Path:
    """Directory for append-only audit/observability sinks."""
    return ops_home() / "audit"


def data_dir() -> Path:
    """Directory for runtime data (confidence snapshots, etc.)."""
    return ops_home() / "data"


def bootstrap_path() -> Path:
    """Path to the environment bootstrap JSON."""
    override = os.getenv("ROGUE_BOOTSTRAP_JSON")
    if override:
        return Path(override)
    return ops_home() / "rogue-ops-bootstrap.json"


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if missing. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path

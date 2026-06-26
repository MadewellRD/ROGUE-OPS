#
# tools/install_hooks.py
#
# Install the ROGUE:OPS git pre-push hook: runs the full test suite before
# every push and aborts the push if anything fails. Run once per clone:
#
#   python tools\install_hooks.py
#
# (The hook itself lives in .git/hooks/ which is not tracked by git, so each
# clone installs it via this script. Override a push with: git push --no-verify)
#

import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".git" / "hooks" / "pre-push"

HOOK_BODY = """#!/bin/sh
# ROGUE:OPS local CI gate (installed by tools/install_hooks.py)
PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"
echo "[pre-push] running ROGUE:OPS test suite..."
"$PY" tools/run_all_tests.py || {
  echo "[pre-push] test suite FAILED - push aborted (use --no-verify to override)."
  exit 1
}
echo "[pre-push] suite green - allowing push."
"""


def main() -> None:
    hooks_dir = HOOK.parent
    if not hooks_dir.exists():
        raise SystemExit(f"No .git/hooks directory at {hooks_dir} (run inside a git clone).")
    HOOK.write_text(HOOK_BODY, encoding="utf-8", newline="\n")
    try:
        HOOK.chmod(HOOK.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass
    print(f"Installed pre-push hook -> {HOOK}")
    print("The full test suite will now run before each push.")


if __name__ == "__main__":
    main()

#
# tools/run_all_tests.py
#
# ROGUE:OPS test runner. Runs the whole suite, each test in its OWN process
# (several tests engage the process-global kill switch, so isolation is
# required). Exits non-zero if any test fails — suitable for CI and local use.
#
#   python tools\run_all_tests.py            (all tests)
#   python tools\run_all_tests.py test_pricing test_market_loop   (subset)
#

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_TESTS = [
    "test_pricing",
    "test_broker_routing",
    "test_indicators",
    "test_market_loop",
    "test_safety_governor",
    "test_fill_pnl",
    "test_massive_client",
    "test_backtest",
    "test_strategies",
    "test_intraday",
    "test_console",
    "test_shadow",
    "run_sim_regression",
]


def _last_line(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def main(argv) -> int:
    tests = argv[1:] or DEFAULT_TESTS
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # A fresh, self-owned ops home per invocation. Tests share it, but each runs
    # in its own process, so only DURABLE cross-process state (the kill / arm
    # files) can leak between them — we clear those before each test to keep the
    # isolation the suite depends on, without weakening the kill mechanism.
    ops_home = env.get("ROGUE_OPS_HOME") or tempfile.mkdtemp(prefix="rogueops_test_")
    env["ROGUE_OPS_HOME"] = ops_home

    def _reset_durable():
        for fn in ("KILL", "ARM"):
            try:
                os.remove(os.path.join(ops_home, fn))
            except OSError:
                pass  # absent, or not ours to remove — fresh temp homes avoid this

    results = []
    for name in tests:
        _reset_durable()
        fname = name if name.endswith(".py") else name + ".py"
        path = REPO / "tools" / fname
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(REPO), env=env, capture_output=True, text=True,
        )
        ok = proc.returncode == 0
        detail = _last_line(proc.stdout) if ok else (_last_line(proc.stderr) or _last_line(proc.stdout))
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<22} {detail}")
        results.append(ok)

    shutil.rmtree(ops_home, ignore_errors=True)
    passed = sum(1 for r in results if r)
    print("-" * 64)
    print(f"  {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

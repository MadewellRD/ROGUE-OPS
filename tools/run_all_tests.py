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
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_TESTS = [
    "test_pricing",
    "test_broker_routing",
    "test_indicators",
    "test_market_loop",
    "test_safety_governor",
    "test_fill_pnl",
    "run_sim_regression",
]


def _last_line(text: str) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def main(argv) -> int:
    tests = argv[1:] or DEFAULT_TESTS
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("ROGUE_OPS_HOME", str(REPO / ".rogueops_test"))

    results = []
    for name in tests:
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

    passed = sum(1 for r in results if r)
    print("-" * 64)
    print(f"  {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

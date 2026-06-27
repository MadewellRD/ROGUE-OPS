#
# tools/shadow_eval.py
#
# Analyze the accumulated shadow ledger: did the LLM's independent read line up
# with the move that followed, vs the deterministic engine?
#
#   python tools\shadow_eval.py            (default: pair gaps up to 30 min)
#   python tools\shadow_eval.py 10         (pair gaps up to 10 min)
#   python tools\shadow_eval.py 30 --json  (machine-readable)
#

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from advisory import shadow_advisor
from research.shadow_eval import score, format_report


def main() -> None:
    gap_min = 30.0
    as_json = "--json" in sys.argv
    for a in sys.argv[1:]:
        if a != "--json":
            try:
                gap_min = float(a)
            except ValueError:
                pass

    rows = shadow_advisor.read_ledger(1_000_000)
    m = score(rows, max_gap_sec=gap_min * 60.0)
    if as_json:
        print(json.dumps(m, indent=2))
        return
    print(f"\n=== ROGUE:OPS shadow ledger evaluation (gap <= {gap_min:.0f} min) ===")
    if not rows:
        print("  ledger empty — run with OLLAMA_SHADOW=1 (live) or tools\\shadow_backtest.py first.")
        return
    print(format_report(m))


if __name__ == "__main__":
    main()

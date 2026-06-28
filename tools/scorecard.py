#
# tools/scorecard.py
#
# Print the ROGUE:OPS track record from the paired-trade ledger.
#
#   python tools\scorecard.py            (human-readable)
#   python tools\scorecard.py --json     (machine-readable)
#

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capital.trade_ledger import read_ledger, scorecard


def _usd(x):
    return "n/a" if x is None else f"${x:,.2f}"


def main() -> None:
    rows = read_ledger(1_000_000)
    m = scorecard(rows)
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2))
        return

    print("\n=== ROGUE:OPS track record (closed trades) ===")
    if not m["trades"]:
        print("  ledger empty — no closed trades yet (paper-forward records here as it trades).")
        return
    wr = m["win_rate"]
    print(f"  trades        : {m['trades']}   (wins {m['wins']} / losses {m['losses']})")
    print(f"  win rate      : {wr * 100:.0f}%" if wr is not None else "  win rate      : n/a")
    print(f"  gross P&L     : {_usd(m['gross_pnl_usd'])}")
    print(f"  expectancy    : {_usd(m['expectancy_usd'])} / trade")
    print(f"  avg win/loss  : {_usd(m['avg_win_usd'])} / {_usd(m['avg_loss_usd'])}")
    print(f"  best / worst  : {_usd(m['best_usd'])} / {_usd(m['worst_usd'])}")
    print(f"  max drawdown  : {_usd(m['max_drawdown_usd'])}")
    if m["by_day"]:
        print("  by day        : " + ", ".join(f"{d} {_usd(v)}" for d, v in sorted(m["by_day"].items())))
    print("  Note: realized-P&L track record; pairs each entry with its exit. Evidence for the go-live gate.")


if __name__ == "__main__":
    main()

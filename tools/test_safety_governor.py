#
# tools/test_safety_governor.py
#
# Proves the daily-loss safety chain is REAL:
#   - SIM is not governed (no accrual)
#   - a governed breach engages the kill switch and reports breached
#   - engage_kill is called with a valid signature (no TypeError)
#
#   python tools\test_safety_governor.py
#

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    import importlib
    import capital.daily_loss_governor as gov
    from governance.kill_switch import kill_active

    # --- A) SIM is not governed: no accrual, no kill ---
    os.environ["EXECUTION_MODE"] = "SIM"
    gov.reset()
    gov.record_realized_pnl(pnl_usd=-100000.0)
    assert gov.current_realized_pnl() == 0.0, "SIM must not accrue P&L"
    assert not kill_active(), "SIM must not engage the kill"
    assert not gov.is_breached(), "SIM is never breached"

    # --- B) Governed breach engages the kill ---
    os.environ["EXECUTION_MODE"] = "CAPITAL"
    os.environ["MAX_DAILY_LOSS_USD"] = "100"
    gov.reset()

    gov.record_realized_pnl(pnl_usd=-60.0)
    assert not gov.is_breached(), "-60 within -100 limit"
    assert not kill_active(), "no kill before breach"

    gov.record_realized_pnl(pnl_usd=-60.0)   # cumulative -120 <= -100
    assert gov.is_breached(), "cumulative -120 must breach -100"
    assert kill_active(), "breach must engage the kill switch"

    print("SAFETY GOVERNOR PASS — SIM ungoverned; governed breach engages kill (valid signature)")


if __name__ == "__main__":
    main()

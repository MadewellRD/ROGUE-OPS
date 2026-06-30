#
# tools/test_options_sizing.py
#
# ROGUE-026: a long option's cash-at-risk is the PREMIUM, not the underlying
# notional (strike * multiplier). Sizing must size on the live premium estimate,
# bounded by the daily-loss cap — so a $5k account CAN buy 1 affordable contract,
# and a too-rich premium is blocked. The pre-fix code divided a tiny budget by
# strike*100 (~$74,500) and zeroed every option trade.
#
#   python tools\test_options_sizing.py
#

import os
import sys
import tempfile
import datetime as dt
from pathlib import Path

os.environ["ROGUE_OPS_HOME"] = tempfile.mkdtemp(prefix="rogue_optsize_test_")
os.environ["MAX_DAILY_LOSS_USD"] = "250"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capital.balance_store import write_snapshot
from capital.account_balance_authority import AccountBalanceSnapshot
from execution.execution_envelope import ExecutionEnvelope
from execution.execution_contracts import ExecutionIntent, OptionSpec
from execution.position_sizing_authority import PositionSizingAuthority
from governance.ops_state import get_ops_state


def _seed_balance():
    write_snapshot(AccountBalanceSnapshot(
        account_id="IBKR", currency="USD",
        net_liquidation=5148.0, available_funds=4592.0, excess_liquidity=4592.0,
        buying_power=18369.0,
        timestamp_utc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        source="CAPITAL", snapshot_hash=None,
    ))


def _paper_entry(strike=745.0):
    intent = ExecutionIntent.new(symbol="SPY", qty=1, action="BUY", sec_type="OPT",
        strategy_tag="T", option=OptionSpec(expiry="20260630", strike=strike, right="C"))
    return ExecutionEnvelope.create(intent=intent, action="ENTRY", execution_mode="PAPER",
        ops_state=get_ops_state().get(), risk_ok=True, authorized=True)


def _size(premium):
    return PositionSizingAuthority.size(
        envelope=_paper_entry(), account_id="IBKR",
        max_contracts=1, max_notional_usd=5000, est_premium=premium,
    )


def test_affordable_premium_allows_one():
    _seed_balance()
    s = _size(1.50)   # $150 outlay <= $250 cap
    assert s.final_quantity == 1, s.sizing_reason


def test_strike_no_longer_zeroes():
    # strike 745 * 100 = $74,500 used to zero everything; premium basis fixes it
    _seed_balance()
    s = _size(2.00)   # 250 // 200 = 1
    assert s.final_quantity == 1, s.sizing_reason


def test_too_rich_premium_blocks():
    _seed_balance()
    try:
        _size(3.00)   # $300 outlay > $250 daily cap -> 0 -> blocked
        assert False, "premium 3.00 (>$250 cap) must block"
    except RuntimeError as e:
        assert "zero" in str(e), str(e)


def main():
    test_affordable_premium_allows_one()
    test_strike_no_longer_zeroes()
    test_too_rich_premium_blocks()
    print("OPTIONS SIZING PASS — premium-based sizing bounded by daily cap; 1 affordable contract; rich premium blocked")


if __name__ == "__main__":
    main()

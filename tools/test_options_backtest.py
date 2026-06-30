#
# tools/test_options_backtest.py
#
# E1 payoff-core test: the Iron Condor settlement P&L is pure + deterministic, so it
# is unit-tested independently of the Massive data path (which is exercised live via
# research.options_backtest.run() in the console container).
#
#   python tools\test_options_backtest.py
#

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROGUE_OPS_HOME", tempfile.mkdtemp(prefix="rogue_optbt_test_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.options_backtest import condor_pnl, summarize

K = dict(net_credit=0.50, short_put_k=735, long_put_k=733, short_call_k=745, long_call_k=747, cost_usd=6.0)


def test_max_profit():
    # spot between the shorts: both spreads expire worthless -> keep full credit - cost
    assert condor_pnl(spot_close=740, **K) == 0.50 * 100 - 6.0


def test_put_side_max_loss():
    # below the long put: put spread loss capped at width 2
    assert condor_pnl(spot_close=730, **K) == round((0.5 - 2) * 100 - 6, 2)


def test_call_side_max_loss():
    assert condor_pnl(spot_close=750, **K) == round((0.5 - 2) * 100 - 6, 2)


def test_partial_breach():
    # 1 point past the short call (width 2): loss = 1
    assert condor_pnl(spot_close=746, **K) == round((0.5 - 1) * 100 - 6, 2)


def test_summarize_tail():
    s = summarize([44.0, 44.0, -156.0])
    assert s["n"] == 3 and s["worst"] == -156.0 and s["best"] == 44.0
    assert s["win_rate"] == round(100 * 2 / 3, 1)
    assert s["expectancy"] == round((44 + 44 - 156) / 3, 2)
    assert summarize([])["n"] == 0


def main():
    test_max_profit()
    test_put_side_max_loss()
    test_call_side_max_loss()
    test_partial_breach()
    test_summarize_tail()
    print("OPTIONS BACKTEST PASS — iron-condor payoff (max-profit / partial / max-loss both sides) + tail summary")


if __name__ == "__main__":
    main()

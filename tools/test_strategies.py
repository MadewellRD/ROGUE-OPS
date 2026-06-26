#
# tools/test_strategies.py
#
# Offline, deterministic tests for the strategy library + backtest engine.
#   python tools\test_strategies.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.strategies import STRATEGIES
from research.engine import simulate, metrics, walk_forward


def req(e9, e21, mh, r7, r14):
    return {"EMA(9)": e9, "EMA(21)": e21, "MACD_Histogram": mh, "RSI(7)": r7, "RSI(14)": r14}


def main() -> None:
    tf = STRATEGIES["trend_follow"]
    assert tf.entry(req(2, 1, 0.5, 55, 55), True) is True
    assert tf.entry(req(2, 1, 0.5, 55, 55), False) is False, "not passed -> no entry"
    assert tf.entry(req(2, 1, 0.5, 72, 55), True) is False, "overbought -> no entry"
    assert tf.exit(req(1, 2, -0.1, 40, 40)) is True, "trend flip -> exit"

    # fail-closed on missing indicators
    assert STRATEGIES["macd_momentum"].entry({}, True) is False
    assert STRATEGIES["rsi_meanrev"].exit({}) is True
    assert STRATEGIES["ema_cross"].exit({}) is True

    # rsi mean-reversion: oversold within up-trend
    assert STRATEGIES["rsi_meanrev"].entry(req(2, 1, 0.0, 25, 40), True) is True
    assert STRATEGIES["rsi_meanrev"].entry(req(2, 1, 0.0, 45, 40), True) is False, "not oversold"

    # ema cross regime
    assert STRATEGIES["ema_cross"].entry(req(2, 1, 0, 50, 50), True) is True
    assert STRATEGIES["ema_cross"].exit(req(1, 2, 0, 50, 50)) is True

    # simulate + metrics: one win, one loss
    rows = [
        {"date": "d1", "close": 100.0, "req": req(2, 1, 0.5, 55, 55), "passed": True},
        {"date": "d2", "close": 110.0, "req": req(1, 2, -0.1, 40, 40), "passed": True},
        {"date": "d3", "close": 110.0, "req": req(2, 1, 0.5, 55, 55), "passed": True},
        {"date": "d4", "close": 99.0,  "req": req(1, 2, -0.1, 40, 40), "passed": True},
    ]
    trades = simulate(rows, tf, cost_bps=0.0)
    assert len(trades) == 2
    assert abs(trades[0].ret - 0.10) < 1e-9 and abs(trades[1].ret + 0.10) < 1e-9
    m = metrics(trades)
    assert m["trades"] == 2 and abs(m["win_rate"] - 0.5) < 1e-9

    # transaction cost reduces returns
    with_cost = simulate(rows, tf, cost_bps=10.0)
    assert with_cost[0].ret < trades[0].ret, "cost must reduce return"

    # walk-forward splits by time
    wf = walk_forward(rows, tf, 0.5, 0.0)
    assert wf["split_at"] == 2 and "in_sample" in wf and "out_of_sample" in wf

    print("STRATEGIES PASS — candidate rules, simulate w/ cost, metrics, walk-forward")


if __name__ == "__main__":
    main()

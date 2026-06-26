# ROGUE:OPS — Edge Roadmap (Phase 8 → capital)

**Premise:** the execution/survival layer is built and verified (deterministic
envelopes, real kill, exact fills, fail-closed pricing, multi-broker, tests, CI,
paper-verified IBKR). The system can *execute and survive* — it does **not yet
have a directional edge**. The SignalEngine is presence-only (it fired on
248/250 bars). This roadmap closes that gap with evidence, and gates capital on
an edge that survives out-of-sample.

## Phase 8 — Find & validate an edge (research, no live risk)

- **8a Strategy framework** — pluggable, value-based strategies (entry/exit from the indicator stack) comparable on one backtest harness. *(this commit)*
- **8b Honest accounting** — transaction costs in the backtest; metrics = win rate, expectancy, cumulative, max drawdown, per-trade Sharpe. *(this commit)*
- **8c Candidate library + ranking** — trend, MACD momentum, RSI mean-reversion, EMA-cross; ranked on real SPY/IWM history. *(this commit)*
- **8d Walk-forward / out-of-sample** — split history; report in-sample vs out-of-sample; **an edge must hold OOS or it doesn't count.** *(this commit)*

## Phase 9 — Promote & gate (live risk, gated)

- **9a Promote** the OOS-validated strategy into the LIVE decision path, replacing presence-only entry, keeping the envelope/risk/exit machinery unchanged. *(gated: a strategy must clear OOS first)*
- **9b Paper-forward** — run the promoted strategy in PAPER on live data; compare realized vs backtest expectation. *(gated)*
- **9c Re-cert + capital** — arm capital only after paper-forward matches expectations and `PHASE25_RECERT.md` is signed. *(gated)*

## Honest data limitation

This Massive tier is **daily** only. The daily harness validates **directional
signal quality on the underlying** — necessary, but *not sufficient* for true
0DTE, which is intraday and option-priced (delta amplification + theta decay).
Faithful 0DTE/option-level backtesting needs intraday + option-quote history (a
Massive/Polygon real-time tier or equivalent). Until then: daily research shapes
and screens the thesis; **true 0DTE validation happens in PAPER (Phase 9b)** on
the live IBKR feed before any capital.

## The discipline

No strategy reaches capital on backtest performance alone. The gate order is:
**survives OOS → behaves in paper → re-certified → armed.** A good-looking
in-sample curve is the easiest way to lose money; this roadmap treats it as a
hypothesis, not a result.

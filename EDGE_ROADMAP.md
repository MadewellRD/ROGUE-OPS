# ROGUE:OPS — Edge Roadmap (ROGUE-008)

**Date:** 2026-06-29   Owner: Will (options approval **Level 3**)   Engineer: Claude
**Premise (unchanged from GO_LIVE_PLAN):** a capital-ready machine ≠ an edge. This
doc is about whether an edge exists, tested evidence-first, before any wiring.

## The decisive result so far: we cannot predict direction

Backtest on 90 days of Massive 5-min RTH bars (55 sessions, 4,271 bars), trend
signal = EMA9/EMA21 + MACD-hist, walk-forward 60/40, 2 bps cost:

| Variant | In-sample (n, ret%, win%) | Out-of-sample (n, ret%, win%) |
|---|---|---|
| Long-only (calls) | 66, **+2.91%**, 45.5% | 48, **−2.29%**, 31.2% |
| Directional (calls **and** puts) | 123, −0.08%, 35.0% | 96, **−4.56%**, 30.2% |

Reading it honestly:

- In-sample-positive flips **negative** out-of-sample → overfit/noise, not signal.
- Adding the short side made it **worse**, not better — so "just add PUTs" is dead.
- This is the **underlying-move proxy.** A real long 0DTE option is *strictly worse*
  (theta decay + bid/ask). So a directional long-call/long-put system on this signal
  **loses money.** This matches every prior test (daily + intraday): breakeven-to-negative.

**Conclusion:** directional prediction is not our edge. Stop trying to time direction.

## What Level 3 actually unlocks (and what it doesn't)

Approved structures (no naked shorts — Level 4 — ever):

- **L2 — long calls/puts:** directional. *Tested: no edge.* Shelved.
- **L3 — debit verticals:** directional but cheaper/defined. Same directional dependency → same problem.
- **L3 — credit verticals / iron condors:** **non-directional.** Monetize *theta* + the
  tendency of an index to stay in a range intraday; **defined max loss** by construction.
  This is the only mechanism left whose edge does **not** depend on predicting direction —
  which is the thing we've repeatedly shown we can't do.

So the one honest shot left is **defined-risk premium/theta capture** (0DTE credit
spreads / iron condors), not direction.

## Why this is a real build, not a tweak

A premium-structure edge needs three things we don't have yet:

1. **Option-priced backtest.** The current harness simulates underlying % moves; it
   cannot see premium, theta, or IV — exactly the things a credit spread lives on. We need
   to backtest on **historical option prices** (Massive Options-Basic has historical option
   aggregates) and model spread entry credit → exit/expiry payoff, **including the tail
   losses** (premium selling = many small wins, occasional max-width losses).
2. **Multi-leg execution.** Today everything is single-leg (`OptionSpec` = one contract).
   Spreads need combo orders, multi-leg pricing, multi-leg sizing under the $250/day cap,
   and multi-leg position tracking + exit. That's a genuine architecture addition.
3. **Honest risk framing.** A defined-risk 0DTE condor can still lose its full width on a
   trend day; the daily-loss kill ($250) must bound a *spread's* worst case, not a single leg.

## Plan (evidence-gated, in order)

| Phase | Work | Gate to advance |
|---|---|---|
| **E1** | Option-priced backtest of a 0DTE credit spread / iron condor on Massive historical option data. Model credit, theta, max-loss tail. | Positive, cost-aware, **out-of-sample** expectancy **with the tail included**. If flat/negative → **stop**; keep the machine as a paper-evidence tool. |
| **E2** | *Only if E1 clears:* multi-leg execution architecture (combo orders, multi-leg sizing/pricing/tracking/exit) behind the existing gates. | Suite green; one paper multi-leg round-trip reconciled. |
| **E3** | Paper-forward the structure; score vs forward returns. | GO/NO-GO per `GO_LIVE_PLAN.md` (1-contract, $250 cap, signed re-cert). |

## Honest bottom line

We've now proven the negative cleanly: **ROGUE can't predict direction, and the short
side doesn't rescue it.** Level 3's real value isn't more directional bets — it's
**defined-risk premium structures** whose edge doesn't require direction. That's worth a
look, but it's a real build that must first clear an **option-priced backtest with the tail
losses included**. Until E1 shows a positive out-of-sample number, **capital stays NO-GO**
and the safest, most honest use of the (now P0-hardened) machine is gathering paper
evidence — not trading.

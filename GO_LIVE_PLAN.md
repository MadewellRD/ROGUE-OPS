# ROGUE:OPS — 2-Week Go-Live Plan (evidence-gated)

> Target: real-money capable by ~2026-07-11. Owner: Will. Engineer: Claude.
> This is a **plan to be *ready*** and to **decide** at a gate — not a promise to
> flip real money on a date regardless of evidence.

## The premise (read first)

Two different things are being conflated in "trading real money in 2 weeks":

1. **A capital-ready machine** — paper-forward live, all gates armed, tiny-size
   live path proven. *Achievable in 2 weeks.*
2. **A proven edge** — a signal that makes money net of costs, out-of-sample.
   *Not manufacturable on a schedule.* Every backtest (daily + intraday) and the
   shadow ledger to date show **breakeven-to-negative**.

The machine executing a no-edge signal loses money efficiently. So go-live here
means: **be ready, gather the best evidence we can in the window, then make a
go/no-go call** — and if we go, go at *tuition* size, fully gated.

This is not financial advice; the decision and the risk are the owner's.

## Go-live definition (what "real money" means here)

CAPITAL mode, with **hard** limits, not aspirations:

| Guardrail | Go-live setting | Where |
|---|---|---|
| Position size | **1 contract** (drop `MAX_CAPITAL_CONTRACTS` 5 → 1) | execution_router |
| Daily loss kill | **$250** (`MAX_DAILY_LOSS_USD`) — confirmed by owner | daily_loss_governor |
| Kill switch | armed, cross-process, console button live | governance/kill_switch |
| Session | RTH only; entries 10:00–14:30 ET; flat 15:55; no overnight | research/intraday rules |
| Preflight | account balance + connectivity check passes | capital_preflight |
| Re-cert | signed checklist (below) before first CAPITAL run | PHASE25_RECERT.md |

If any guardrail isn't live, CAPITAL stays disabled. Fail-closed.

## Sequence

### Week 1 — capital-ready plumbing + start evidence
| # | Owner | Action | Gate |
|---|---|---|---|
| 1 | Will | Allow `docker` in signaldesk exec policy | done = I can build/run |
| 2 | Will | IB Gateway **paper** up @4002, API on, trusted IP; vendor `ibapi` | Gateway reachable |
| 3 | Claude | Bring up paper container; verify live IBKR data + one paper fill end-to-end | green = paper loop real |
| 4 | Claude | Run paper-forward during RTH with `OLLAMA_SHADOW=1`; P&L + ledger accrue | daily logs |
| 5 | Claude | Set the go-live guardrails (size→1, daily-loss=$___, preflight wired) behind CAPITAL | suite green |

### Week 2 — richer data + edge verdict
| # | Owner | Action | Gate |
|---|---|---|---|
| 6 | Will | Massive upgrade (paid) → options/IV/intraday; restore GitHub CI | data + CI live |
| 7 | Claude | Re-run research on the richer data — options skew / IV / flow, where 0DTE edge actually plausibly lives | edge report |
| 8 | Claude | Score accumulated paper-forward + shadow ledger vs forward returns | honest verdict |
| 9 | Both | **GO / NO-GO** (criteria below) | decision |

### Day ~14 — the gate
**GO (to 1-contract CAPITAL)** only if ALL hold:
- a research signal with **positive out-of-sample, cost-aware** expectancy on the upgraded data, and
- paper-forward over the window is **not** net-bleeding, and
- preflight + signed re-cert + kill + daily-loss cap are all live.

**NO-GO (stay on paper)** if the evidence is flat/negative. Going live on no edge
is paying the market to confirm you have no edge. NO-GO is a *success* of the
process, not a failure of the timeline.

## Capital preflight / re-cert checklist (sign before first CAPITAL run)
- [ ] IBKR account = the intended one; buying power confirmed; **paper→live port** change is deliberate.
- [ ] `MAX_CAPITAL_CONTRACTS = 1`; daily-loss kill = `$250` (`MAX_DAILY_LOSS_USD`); both unit-tested.
- [ ] Kill switch verified live (console button halts the loop on the box).
- [ ] Preflight passes (balance + connectivity); fail-closed on failure.
- [ ] One real 1-contract round-trip observed and reconciled (fill price → P&L → governor).
- [ ] Owner has read the edge verdict and accepts the risk at this size.
- [ ] Re-cert signed + dated.

## What I needed from you (now resolved)
1. ~~`docker` exec permission~~ — **done** (policy root added; `docker` 29.5.2 reachable).
2. ~~IB Gateway paper @4002 + `vendor/ibapi`~~ — **done** (Gateway connected, 78 live bars pulled; `ibapi` installs from PyPI — no host vendoring needed).
3. ~~Daily-loss number~~ — **set: $250** (`MAX_DAILY_LOSS_USD`, wired into the paper loop's governor).

## Honest bottom line
In 2 weeks you can have a real-money-*capable*, fully-gated, 1-contract system and
a real edge verdict. Whether you pull the trigger should depend on that verdict.
I'll build all of it and hold every gate; I won't fake an edge to hit a date.

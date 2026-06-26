# ROGUE:OPS — Phase 3 Summary

_Hardening the live path from façade to verifiable. Engineering record._

## Context

A review found that ROGUE:OPS, despite production-grade governance documentation,
was effectively a **SIM demonstrator**: the autonomous live pipeline was wired by
name but broke on the first market tick, the strategy layer had no strategies,
and the capital-safety controls that justified go-live were mostly inert. The
broker layer was the first example — order execution was called but never
implemented. It turned out to be a pattern, not an exception.

Phase 3 converted the live path from aspirational to **verifiable**, and stood up
the first real automated test suite the system has ever had.

## What changed

**Multi-broker boundary (kept IBKR, added Robinhood).** A single `BrokerRuntime`
interface with capability-aware, fail-closed routing: options → IBKR, equities →
Robinhood, and a hard block if an instrument is routed to a broker that can't
trade it. IBKR's options order path was built and **verified on live paper TWS**.

**Marketable-limit pricing.** 0DTE options now price off the live NBBO and the
adapter **refuses to send a naked market order** when it can't get a quote.

**P3a — honest live loop.** Rewrote the market loop onto the proven SignalEngine
path (market → indicators → signal → state machine → execution), fixed the
`MarketSnapshot` type crash, and wired the exit path that never ran in
production. Fixed seven integration defects where called code didn't match (or
didn't exist on) its target — including entries that silently blocked themselves
and an exit engine that crashed on a missing argument.

**P3b — real capital safety.** Consolidated realized P&L into one source of
truth, fixed a kill-switch call that would have crashed at the exact moment a
loss-limit breach fired, and made the daily-loss kill actually engage and block
further entries. Aligned the contract limit to the signed authorization (5).

## Measurable impact

- **9 critical/high integration defects** identified and fixed across execution, safety, and market data.
- **Entry → exit lifecycle**: from structurally impossible (positions could open but never close) to verified end to end.
- **Daily-loss kill**: from theater (two disconnected trackers, a crash on breach) to proven-firing.
- **Automated tests**: from **0** real assertions to a **4-test suite** guarding pricing, broker routing, the full trade lifecycle, and the safety kill — plus the existing SIM regression.
- **Cross-platform**: SIM stands up on Windows with zero cloud dependency.

## Verification

```
test_pricing          PASS   marketable limit, buffer, tick rounding, fail-closed
test_broker_routing   PASS   capability routing + fail-closed guards
test_market_loop      PASS   signal -> sized entry -> managed exit -> IDLE
test_safety_governor  PASS   governed breach engages kill; SIM ungoverned
run_sim_regression    PASS   deterministic SIM invariants intact
```

## What remains

- **IBKR option fill** verified on paper during market hours; then re-sign `PHASE25_RECERT.md` before any capital (execution-path changes invalidated the prior authorization by design).
- **Robinhood equities** go live once the agentic-account OAuth token is minted and the live tool schema is confirmed via the probe.
- **Market feed enrichment** (next): the live feed is spot-only, so VWAP and ATR can't yet be computed; enriching it restores those to the signal contract.
- **Dead-code prune**: `git rm` the confirmed-dead modules (arbitration/engine.py, arbitration/capital_gate.py, execution/sizing_engine.py, arbitration/types.BROKEN.py).

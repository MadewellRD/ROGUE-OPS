# ROGUE:OPS — Architecture Review & Action Plan

_Prepared as the engineering owner's review. Scope: whole system, with the same
façade-hunting rigor that surfaced the IBKR order-path gap._

---

## 1. Bottom line

ROGUE:OPS today is a **SIM demonstrator wrapped in production-grade governance
language.** Exactly one path produces a trade — the hardcoded
`SignalEngine → sim_trade_driver` path. The autonomous live pipeline
(market loop → council → arbitration → execution → broker → exit) is wired *by
name* but breaks on the first real market tick; the "strategy council" has **no
strategies to run**; and most of the capital-safety controls that justify the
Phase 25 go-live authorization **do not fire**.

The IBKR broker façade found earlier was not an outlier — it is the dominant
pattern across the codebase: well-formed modules with elaborate docstrings, and
broken or missing integration *between* them. Caller/callee signatures have
drifted, several subsystems are duplicated (one live, one dead), and nothing was
ever integration-tested across module boundaries.

**This is fixable, and the bones are good** (clean `ExecutionEnvelope` /
`ExecutionIntent` data contracts, a real kill switch, and — as of this work — a
working broker boundary and a paper-verified IBKR order path). But it must be
treated as **pre-integration, not pre-launch.**

Severity tally: **5 Critical, 4 High**, plus medium/hygiene items below.

---

## 2. What actually works today (verified, not claimed)

- **SIM pipeline** end to end: signal → sealed envelope → sized → `SUBMITTED`, deterministic; regression-green.
- **Kill switch** — real, process-dominant, checked at router and state machine. The one safety control that genuinely fires.
- **Multi-broker boundary + capability routing** — built this cycle; fail-closed (options can't route to Robinhood); unit-tested.
- **IBKR live order path** — built and **verified on paper TWS** (equity → `PreSubmitted`); order-id sequencing and order-status capture confirmed against real TWS.
- **Marketable-limit pricing** for options — prices off live NBBO, **refuses naked market orders** when unpriceable.
- **Cross-platform standup** — SIM boots on Windows with zero cloud dependency; PAPER/LIVE still fail-closed without their config.
- **Envelope sealing/verification + intent data model** — sound and correctly used.

---

## 3. Critical defects (will not run, or loses safety)

**C1 — The live market loop crashes on the first tick.** Two different
`MarketSnapshot` types collide: `market_loop.py` builds
`market.types.market_snapshot.MarketSnapshot` (`snapshot_id`, `raw_primary`,
`primary_symbol`) while `get_market_snapshot()` returns
`market.market_data.MarketSnapshot` (`symbol`, `source`, `meta`). PAPER/LIVE/
CAPITAL have therefore never run past the first snapshot. _(market/market_loop.py:96-103)_

**C2 — Entry-only architecture: positions can open but never close.**
`manage_position()` (the exit trigger) is never called from the live loop —
only from test/replay harnesses. `intent_router.route()` handles ENTRY only. So
`exit_engine`, `Position.to_exit_intent()`, and the `on_position_closed` /
`on_audit_complete` lifecycle callbacks are all unreachable in production.
_(execution/state_machine.py, execution/intent_router.py)_

**C3 — Caller/callee signature drift on the live and safety paths:**
- `state_machine` calls `evaluate_capital_gate(intent=, ops_state=)`; the function takes `(envelope)` → TypeError on CAPITAL entry. _(state_machine.py:142)_
- `state_machine` calls `exit_engine.evaluate()` without the required `indicators` arg → exit crashes. _(state_machine.py:204)_
- `execution_driver` calls `record_realized_pnl(account_id=, envelope=)`; it takes `(pnl_usd)` → realized PnL is **never recorded**. _(execution_driver.py:131)_
- `execution_driver` references `envelope.id`, which doesn't exist (`envelope_hash`) → the error path itself crashes. _(execution_driver.py:104)_
- The live entry path appears to call `execute()` (EXIT-guarded) rather than `execute_sized()` (ENTRY); if so, **all entries are blocked** as `UNSIZED_ENTRY_FORBIDDEN`. **Needs a definitive trace and fix.**

**C4 — Capital safety is largely theater.** If armed for CAPITAL today: the kill
switch fires, but the **daily-loss hard lock does not** (two disconnected PnL
trackers — `risk_engine._DAILY_PNL_USD` is never written; the
`daily_loss_governor` write is broken by C3), and the **capital gate**
(promotion / kill-drill / go-no-go) **does not fire on entry** (signature
mismatch makes it unreachable; it's only checked once at startup preflight).
`RiskEngineV2.pre_trade_check` runs but its PnL input is never fed.
_(governance/risk_engine.py, capital/daily_loss_governor.py, capital/capital_gate.py)_

**C5 — The strategy layer has nothing to run.** `StrategyRegistry.discover()` is
a no-op `return`; there are **zero concrete strategy implementations** in the
repo; and the `base.evaluate() → List[StrategyIntent]` return type is
incompatible with what the council consumes (`ExecutionIntent`/
`ObservationIntent`), with no conversion layer. Even if the loop ran, the
"intelligent" path would produce no proposals. _(strategy/registry.py:73-82, strategy/base.py, strategy/council/council_engine.py)_

---

## 4. High-severity defects

**H1 — Audit is not persistent.** The hash chain is implemented but stored in an
in-memory list (`audit_store.py:48`); it's lost on restart. The go-live doc's
"append-only, tamper-evident, fully reconstructable" is therefore false across
process death. Arbitration decisions are never logged (the sink exists, is never
called), and there are two uncoordinated audit systems (in-memory chain vs JSONL
sinks).

**H2 — The replay path won't even import.** `replay_engine.py` uses unqualified /
nonexistent imports (`from intent_authority import ...` — no such module). The
"Replay → Live parity certified" claim is impossible; replay doesn't load.

**H3 — The feedback system is orphaned.** `StrategyFeedbackStore` is created but
never passed into the loop; the emit pathway lives only in the dead arbitration
engine; council confidence is hard-coded to 0. The entire learning loop is inert.

**H4 — Dead/competing implementations (landmines).** `arbitration/engine.py`
(dead) vs `arbitration_engine.py` (live); `arbitration/capital_gate.py` (dead) vs
`capital/capital_gate.py` (live); `sizing_engine.py` (dead) vs
`position_sizing_authority.py` (live); `types.BROKEN.py` left in tree. Each is a
future foot-gun.

---

## 5. Medium / hygiene

- Observation/cadence layer (`observation/*`) is fully orphaned — dormant by design; decide keep-or-cut.
- `paper_trade_driver.py` validates entry only, never exit.
- Audit writes silently swallow I/O errors — failures are invisible.
- **No CI and no cross-boundary integration tests** — the root-cause enabler for everything above.

---

## 6. Root cause

Module-first construction with phase-numbered documentation, **never
integration-tested across boundaries.** The governance documents describe the
*intended* system; the code is a collection of individually plausible parts that
were never wired and exercised together. The tells are everywhere: signature
drift between callers and callees, duplicated engines, entry-only wiring, and an
in-memory audit store behind a "tamper-evident forensics" claim.

---

## 7. Sequenced roadmap (each phase has a hard exit criterion)

**P3a — Make the live loop honest (no crash; entry + exit wired).**
Unify `MarketSnapshot` to one type; wire `manage_position` into the loop for open
positions; resolve the `execute()` vs `execute_sized()` entry/exit split; fix the
four C3 signature mismatches.
_Exit:_ a PAPER dry-run drives market → signal → envelope → broker **entry** and a
managed **exit** on paper TWS, with audit records — proven by an integration test.

**P3b — Make safety real (HARD BLOCKER before any CAPITAL).**
One source of truth for realized PnL; wire `record_realized_pnl` correctly; make
the daily-loss kill actually engage; enforce the capital gate per-entry with the
correct signature (promotion / kill-drill / go-no-go reachable); feed RiskEngine's PnL.
_Exit:_ an automated test proves a daily-loss breach engages the kill and blocks
further entries, and the capital gate blocks when unarmed/expired. Then re-sign
`PHASE25_RECERT.md`.

**P3c — Decide the strategy story (your call — see §8).**
Either standardize on the working `SignalEngine` path and shelve the
council/arbitration/feedback scaffolding, or invest in ≥1 real strategy + fix the
type contract + wire feedback.
_Exit:_ a single, documented decision path from market data to a proposed intent.

**P3d — Audit persistence + forensics.** Persist the hash chain (append-only
file/DB), log arbitration, unify the two audit systems, stop swallowing failures.
_Exit:_ kill the process mid-run and fully reconstruct the session from disk.

**P3e — Replay parity (only if you want the claim).** Fix replay imports; make
replay run the *same* execution path; then "parity certified" is earned, not asserted.

**P3f — Test/CI harness.** Cross-boundary integration tests (the thing that would
have caught all of §3–§4) plus a CI gate. This is the durable fix for the root cause.

---

## 8. Decisions for you

1. **Strategy layer:** standardize on the working `SignalEngine` path (recommended — fastest route to a defensible live system) or invest in the council/arbitration build-out as a deliberate future bet?
2. **First live milestone:** a paper-only proving run first (strongly recommended) before any CAPITAL arming?
3. **Broker scope now:** IBKR options only first, or push the Robinhood equities transport in parallel?
4. **Surface area:** keep observation/cadence + replay, or cut them to shrink what has to be made correct?

---

## 9. Hard go-live gates (now explicit)

No CAPITAL arming until **all** of: live-loop entry+exit verified on paper; the
daily-loss kill proven to fire by test; the capital gate enforced per-trade;
audit persisted and reconstructable; `PHASE25_RECERT.md` signed. The kill switch
is already real and need not be rebuilt — everything else in the safety story
must be made true before it can be trusted with money.

# ROGUE:OPS — Audit Remediation Tracker (evidence-gated)

> Source of findings: `CODEBASE_AUDIT.md` (2026-06-29). Owner: Will. Engineer: Claude.
> Same contract as `GO_LIVE_PLAN.md`: this tracks **work to be *ready*** and the
> **gates** that prove each item is actually fixed — not checkboxes ticked on faith.
> A finding is **Done** only when its Gate is demonstrated (test, probe, or grep), not when code is written.

## Status legend
`☐ To-do` · `◐ In progress` · `☑ Done (gate met)` · `⏸ Blocked / needs owner`

## Scoreboard
| Priority | Meaning | Open | Done |
|---|---|---|---|
| **P0** | PAPER can trade & close safely (before trusting any paper result) | 2 | 3 |
| **P1** | Required before any CAPITAL plumbing exposure | 5 | 1 |
| **P2** | Hygiene / de-risk / surface reduction | 13 | 1 |

> **Progress 2026-06-29:** ROGUE-004 ☑ (ws_server deleted), ROGUE-009 ☑ (ARM now enforced
> in `authorize_entry` via `governance/arm_switch`; `test_arm_gate` added), ROGUE-001 ☑
> (sizing reads `balance_store`; verified $5,148 netliq in-container). **Note:** the loop is
> deliberately left **DISARMED** — do not ARM for live paper trading until ROGUE-002/003
> (safe exits) land, or a slow fill will crash the loop. ROGUE-008 greenlit
> (build real directional logic). New: ROGUE-024 (Massive WebSocket feed).
>
> **Progress 2026-06-30 (ARMED, live):** pipeline proven end-to-end during RTH — Gateway
> auto-reconnect (ROGUE-003 ☑ live), live moving data, balance read (ROGUE-001 ☑ live),
> signal fired, every gate cleared. **ROGUE-026 (new, P0):** option sizing used underlying
> notional (strike×100 ≈ $74.5k) → 0 contracts for any account under ~$3.7M; fixed to size a
> long option on its **premium** bounded by the $250 daily cap (code + `test_options_sizing`,
> 23/23 green). First real entry is now gated only by market hours: it missed today's 14:30 ET
> cutoff (correct 0DTE rule) and will **auto-enter at tomorrow's 10:00–14:30 ET window** —
> armed, always-up, no intervention. ROGUE-026 live + ROGUE-015 round-trip verify at that entry.

> Reminder (carried from GO_LIVE_PLAN): plumbing readiness ≠ edge. **ROGUE-008** (no
> directional logic / no proven edge) is the real CAPITAL gate and is independent of
> every fix below. A perfectly-wired machine on a no-edge signal still bleeds.

---

## P0 — make PAPER actually trade & close safely
| ID | Owner | Action | Gate (done = ) | Status |
|---|---|---|---|---|
| ROGUE-001 | Claude | Sizing reads the **wrong cache**. Point `position_sizing_authority` at `balance_store.get_snapshot(...)` (as `capital_preflight.py:129` already does), or hydrate `_CACHED_SNAPSHOT` from SQLite. | In-container `get_cached`/sizing returns a real balance; a PAPER ENTRY produces qty≥1 instead of `BALANCE_CACHE_EMPTY`. | ☑ verified: `get_cached_snapshot` → $5,148 netliq in `rogue-loop` |
| ROGUE-002 | Claude | EXIT fill-missing raises **uncaught** and crashes the loop. Wrap the EXIT path; add `on_exit_failed` (mirror `on_entry_failed`); reconcile/cancel the working order before retry. | Forced no-fill exit: loop survives, state reverts, order cancelled, position not stranded. New test green. | ☑ `on_exit_failed` + driver try/except; `test_exit_recovery` |
| ROGUE-003 | Claude | **No cancel, no reconnect** anywhere. Add cancel-on-timeout (`cancelOrder`/`reqGlobalCancel`); add reconnect + re-subscribe; wire `classify_ibkr_error`. | Timed-out order is cancelled at broker; simulated disconnect auto-reconnects and resumes. | ☑ cancel-on-no-fill (`cancel_order` + recheck) + reconnect watchdog (1101/1102 health); validated connects cleanly — forced-drop reconnect not yet observed |
| ROGUE-015 | Claude | Tests are **SIM-only** → masked ROGUE-001/002. Add an integration test driving a real PAPER entry→exit round-trip (mocked broker fills incl. no-fill + partial). | Test in `tools/run_all_tests.py`, green, exercises the live lifecycle (not just SIM). | ◐ exit lifecycle covered (`test_exit_recovery`); full live PAPER round-trip still pending |

## P1 — required before any CAPITAL exposure
| ID | Owner | Action | Gate (done = ) | Status |
|---|---|---|---|---|
| ROGUE-004 | Claude | Delete orphaned `api/ws_server.py` (network trade-executor with committed `CHANGE_ME` HMAC). | File removed; `grep ws_server` clean; suite green. | ☑ deleted |
| ROGUE-005 | Claude | No auth on `/control/*`. Add a shared-secret/token check (kill/clear_kill/arm); tighten CORS. | Unauthenticated POST to `/control/*` is rejected; console sends the token. | ☐ |
| ROGUE-006 | Claude | Partial fills booked as full closes. Inspect `remaining`; reconcile quantity. | Partial fill is not treated as a complete close; qty reconciled. New test. | ☐ |
| ROGUE-007 | Claude | ENTRY no-fill strands an untracked real position. Cancel-on-timeout + late-fill reconciliation. | After an entry timeout, no untracked position can exist (order cancelled or tracked). | ☐ |
| ROGUE-013 | Claude | `clear_kill` is unauthenticated (folds into ROGUE-005). | `clear_kill` requires the token; durable kill not clearable from an unauthenticated caller. | ☐ |
| ROGUE-008 | Will + Claude | **The real gate: no edge.** Decide — build genuine directional logic (PUTs, EMA/MACD/RSI/VWAP signs) or accept the NO-GO and stay paper. | A written edge verdict on the best available data; CAPITAL decision made on it, not on plumbing. | ⏸ |

## P2 — hygiene, de-risk, surface reduction
| ID | Owner | Action | Gate (done = ) | Status |
|---|---|---|---|---|
| ROGUE-020 | Claude | Delete retired subsystems: `arbitration/`, `strategy/`+council/feedback/observation/context, `audit/`, `observation/`, `LAW/`+`laws/`, `sim_golden/` (~2.5k LOC, 0 live). | Dirs removed; import graph + suite green. | ☐ |
| ROGUE-021 | Claude | Delete dead advisory layer: `option_selector`, `pricing_authority` (stale copy of old driver), `option_qualifier`, `intent_authority`, `qualified_contract`, `greeks_overlay`, `confidence_engine`, `parity_*`, per-indicator `*_authority`. | Removed; suite green; no live import lost. | ☐ |
| ROGUE-022 | Claude | Delete orphaned/broken modules calling nonexistent methods (`ibkr_balance_collector`, `ibkr_option_discovery`) + unused (`ibkr_errors`, `contract_cache`, `ibkr_runtime_entrypoint`, dead `governance/*`) + legacy `main.py`. | Removed; suite green. | ☐ |
| ROGUE-010 | Claude | Remove dead duplicate P&L accumulator in `risk_engine.py` (hardcoded $250). | One P&L authority (the governor); no dead accumulator. | ☐ |
| ROGUE-014 | Claude | Unify balance `source` semantics (runtime writes CAPITAL; collector wrote PAPER). | Single consistent `source`; preflight check unambiguous. | ☐ |
| ROGUE-009 | Will + Claude | Console **ARM is cosmetic** → **now enforced.** `governance/arm_switch.arm_active()`; `authorize_entry` denies PAPER/CAPITAL entries when disarmed (SIM exempt). | No entry while disarmed; `test_arm_gate` green. | ☑ enforced |
| ROGUE-011 | Claude | Strike uses a **stale** last-bar close. Use a fresh quote midpoint for strike selection. | Strike derived from a current quote, not a stale bar. | ☐ |
| ROGUE-012 | Claude | Connection multiplicity / clientId churn (singleton + per-fetch `_HistClient`). Reuse one connection. | Single IBKR client for data+exec; stable clientId; reconnect path. | ☐ |
| ROGUE-023 | Claude | Prune/refresh stale docs (PHASE25_RECERT, PHASE3_SUMMARY, CAPITAL_GO_LIVE_AUTHORIZATION, ACTION_PLAN, EDGE_ROADMAP, CODEBASE_REVIEW). | Docs reflect reality; no false claims (e.g., "sizing reads the store"). | ☐ |
| ROGUE-016 | Claude | `LAW_VERSION_HASH` placeholder baked into the seal. Wire a real version or drop the pretense. | LAW version is real or removed. | ☐ |
| ROGUE-017 | Claude | `Position.opened_at_utc` naive `utcnow()` vs tz-aware elsewhere. | tz-aware throughout. | ☐ |
| ROGUE-018 | Claude | Live balance `snapshot_hash=None` (audit fidelity). | Hash computed for live snapshots. | ☐ |
| ROGUE-019 | Claude | Containers reach host Ollama `:11434` (advisory-only). Confirm intended; document. | Documented/scoped; no action if accepted. | ☐ |
| ROGUE-024 | Will + Claude | **Massive WebSocket** real-time feed (the WS actually wanted; the deleted `ws_server` was unrelated). Stream live quotes to replace the stale last-bar spot (also addresses ROGUE-011). **Verify Massive WS entitlement on the current tier first.** | Live WS quotes feed the loop; strike derived from a real-time price, not a stale bar. | ☐ |

---

## Sign-off checklist (before P0 is declared complete)
- [ ] ROGUE-001 — a real PAPER ENTRY sizes and submits (observed in `rogue-loop`).
- [x] ROGUE-002 — a forced no-fill EXIT recovers cleanly; loop does not crash. (`test_exit_recovery`)
- [~] ROGUE-003 — cancel-on-no-fill + reconnect watchdog implemented & live; forced-disconnect reconnect not yet observed.
- [ ] ROGUE-015 — PAPER entry→exit integration test is in the suite and green.
- [ ] One full paper round-trip observed end-to-end (signal → order → fill → P&L → governor → ledger).

## What I need from you (owner decisions)
1. **ROGUE-008 (edge):** do you want me to attempt real directional logic, or hold at NO-GO and keep gathering paper evidence? This is the capital decision, not a code fix.
2. **ROGUE-009 (ARM):** should the console ARM button *enforce* (block PAPER entries until armed), or be removed? Right now it does nothing.
3. **ROGUE-004 (ws_server):** confirm I can delete it outright (recommended) — nothing live imports it.

## Honest bottom line
The safety chassis is sound; the drivetrain is not connected and has no edge. **P0** is the difference between "looks live" and "actually trades and closes safely in paper." **P1** is the bar for trusting the capital *plumbing*. **ROGUE-008** is the bar for trusting the *strategy* — and nothing in P0/P1/P2 manufactures it. NO-GO on capital remains the correct default until that verdict exists.

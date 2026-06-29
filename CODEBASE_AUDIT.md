# ROGUE:OPS — Full Codebase Audit

**Date:** 2026-06-29   **Auditor:** automated multi-agent review (4 parallel domain audits + import-closure analysis + live in-container probes)
**Scope:** entire repository, with emphasis on the live PAPER/CAPITAL execution path.
**Method:** read real source (not the truncating sandbox mount), built an AST import-closure graph, ran the test suite, and probed the running `rogue-loop` container for ground truth. Every finding cites `file:line`.

---

## 0. Verdict

| Question | Answer |
|---|---|
| Is the safety/gating spine well-built? | **Yes** — kill dominance, sealed+hashed envelopes, daily-loss governor, layered CAPITAL gate are genuinely sound. |
| Can it place a PAPER trade today? | **No.** Sizing reads a cache nothing fills (ROGUE-001). Confirmed live: `BALANCE_CACHE_EMPTY`. |
| Can it safely *close* a trade? | **No.** A slow/partial fill crashes the loop and strands a live, uncancellable order (ROGUE-002/003). |
| Is there a trading *edge*? | **No.** The "signal" is a presence check that always buys a call, with no directional logic (ROGUE-008). |
| Real-money (CAPITAL) go-live? | **NO-GO.** Fix ROGUE-001..005 first; there is no evidence of edge regardless. |
| How much of the codebase is live? | **~55 of 183 app modules (~30%).** The rest is research, tests, or **dead scaffolding** from retired architectures. |

**One honest correction to the record:** earlier this session I reported the PAPER balance-sizing path as "fixed." It is **not**. I verified `balance_store.get_snapshot` (SQLite) had data, but sizing actually calls `AccountBalanceAuthority.get_cached_snapshot`, which reads a *different*, in-process cache that only SIM fills. I verified the wrong object. The audit caught it; it is logged as ROGUE-001.

---

## 1. What is WIRED and SOUND (credit where due)

The defensive architecture is real and well-implemented:

- **Kill-switch dominance** — `governance/kill_switch.py`. In-process flag OR `OPS_KILL_SWITCH` env OR durable `KILL` file; fail-closed on error; irreversible in-process; re-checked at every authority boundary (envelope `execution_envelope.py:113`, router `execution_router.py:124,177`, sizing `position_sizing_authority.py:66`, driver `execution_driver.py:54`, loop `market_loop.py:150`). **Cross-process verified**: console KILL in one container halts the loop in the other via the shared `/data/KILL`.
- **Envelope sealing** — `execution/execution_envelope.py`. Frozen dataclass, dual SHA-256 (content + seal), canonical JSON; `verify_seal()` is called first in both router entrypoints before any broker contact; tamper → blocked.
- **State machine** — `execution/state_machine.py`. Guarded transitions; illegal transition → `engage_kill`; `authorize_entry` enforces IDLE + kill/halt + one-position + entry-window + risk pre-check. `on_entry_failed` reverts a failed entry to IDLE (deadlock fix this session is correct *for entry*).
- **Daily-loss governor** — `capital/daily_loss_governor.py`. Single source of truth, engages kill on breach, defaults to a protective $250 when env is invalid, SIM/REPLAY ungoverned. Wired into the live EXIT path.
- **CAPITAL gate** — `capital/capital_gate.py` + `go_no_go_gate.py` + `capital_preflight.py`. Layered fail-closed: OPS clear, env consistency, `CAPITAL_ARMED`, go/no-go attestation, kill-drill recency, balance preflight (reads SQLite correctly).
- **Router backstops** — `execution/execution_router.py`. Mode caps (default 1 contract / $5k notional, env-overridable), post-sizing notional recheck, ENTRY-sized / EXIT-unsized enforced.
- **Option pricing (at the broker)** — `broker/ibkr_broker.py` + `broker/pricing.py`. Builds the 0DTE contract, pulls live NBBO, computes a marketable LIMIT (BUY=ask), **refuses a naked market order** if unpriceable unless `ROGUE_FORCE_MKT=1`; handles delayed ticks 66/67 so a paper account without OPRA can still price.
- **Shadow LLM advisor** — `advisory/shadow_*`, `llm_ollama.py`. Provably isolated: off by default, daemon thread, fail-soft, log-only, and import-isolated from `execution/` and `capital/`.
- **Secrets hygiene** — `.env`, `.massive_key` are gitignored and `.dockerignore`'d (not baked into images); no key literals committed; no S3/AWS code present.
- **Config/bootstrap** — `ops_config.py` + `governance/bootstrap_env.py`. Hard-gates LIVE; requires `IBKR_ACCOUNT_ID` for PAPER/LIVE; fail-closed on missing.

---

## 2. CRITICAL findings (block paper *and* capital)

**ROGUE-001 — PAPER/CAPITAL sizing reads a cache nothing populates → zero trades.**
Sizing calls `AccountBalanceAuthority.get_cached_snapshot(account_id="IBKR")` (`position_sizing_authority.py:93-97`), which reads the module global `_CACHED_SNAPSHOT` (`account_balance_authority.py:175-179`, declared `:57`). That global is assigned in exactly one place — the **SIM-only** producer (`:142-144`). The IBKR runtime instead writes **SQLite** via `balance_store.write_snapshot` (`ibkr_runtime.py:343`). The two never connect, so every non-SIM ENTRY raises `RuntimeError("BALANCE_CACHE_EMPTY")`. **Confirmed live** in `rogue-loop`. Fails closed (no mis-sized order) but PAPER can never enter.
**Fix:** point sizing at `balance_store.get_snapshot(...)` (exactly what `capital_preflight.py:129` already does), or hydrate `_CACHED_SNAPSHOT` from SQLite. Then verify a real PAPER ENTRY end-to-end.

**ROGUE-002 — EXIT fill-missing crashes the loop and strands a live order.**
`wait_for_fill` returns `None` on a ~6s timeout (`ibkr_runtime.py:193-204`); that `None` becomes `fill_price=None` → `handle_exit` raises `EXIT_FILL_PRICE_MISSING` (`execution_position_bridge.py:121-123`). The EXIT branch in `execute_and_apply` (`execution_driver.py:138-146`) and `market_step` (`market_loop.py:62-68`) have **no try/except**, and the loop catches only `KeyboardInterrupt/SystemExit` (`market_loop.py:214`). Net: the **exit order is already submitted** but the loop thread dies, the position stays "open," and the state machine is stuck in `EXITING_POSITION`. For 0DTE, a slow fill is routine, not an edge case.
**Fix:** wrap the EXIT path; add `on_exit_failed` recovery (mirror `on_entry_failed`); reconcile/cancel the working order before retry.

**ROGUE-003 — No order cancellation and no reconnection anywhere.**
`broker/` has `placeOrder` but **no `cancelOrder`/`reqGlobalCancel`** (grep-confirmed). A timed-out order is left working (DAY tif). On disconnect, `error()` sets `_connected=False` (`ibkr_runtime.py:276-277`) but nothing reconnects; `classify_ibkr_error` (`ibkr_errors.py`) is never called. A drop is permanent until process restart, losing in-flight order/fill state.
**Fix:** cancel-on-timeout; add reconnect + re-subscribe; wire `classify_ibkr_error`.

**ROGUE-004 — Orphaned `api/ws_server.py` is a network-listening trade executor with a committed secret.**
Binds `0.0.0.0:8765` (`:13`), hardcodes `SHARED_SECRET = b"CHANGE_ME_TO_REAL_SECRET"` (`:17`), and has an EXECUTION_ENVELOPE handler that runs `ENTRY_AUTHORIZED`/`EXIT_NOW` (`:117-143`). Not wired today, but anyone who runs it ships a remotely-triggerable order executor with a public HMAC key.
**Fix:** delete it (or move out of the package). It is pure liability.

**ROGUE-005 — No authentication on any `/control/*` endpoint.**
`/control/kill`, `/control/clear_kill`, `/control/arm` have zero auth (`terminal_server.py:111-124`); `Access-Control-Allow-Origin: *` (`:49`). Safety today rests **entirely** on the loopback port-map (`docker-compose.yml:19` → `127.0.0.1:8787`), while the container binds `0.0.0.0`. One compose/bind edit exposes KILL/ARM/research to the LAN.
**Fix:** add a shared-secret/token check on `/control/*` as defense-in-depth; don't rely on bind scope alone.

---

## 3. HIGH findings

**ROGUE-006 — Partial fills mis-treated as full closes.** `fill_price` returns on any positive `avgFillPrice` (`ibkr_runtime.py:186-191`); `remaining` is never inspected (`:149-170`). A partial fill is booked as a complete close with no quantity reconciliation.

**ROGUE-007 — ENTRY no-fill strands an untracked real position.** On entry timeout the driver logs, calls `on_entry_failed`, returns False (`execution_driver.py:126-130`) — but the order was already submitted (`execution_router.py:241`). If it later fills, a real position exists with zero engine tracking.

**ROGUE-008 — There is no strategy/edge; the "signal" is a presence check.** `SignalEngine.evaluate` fires when symbol∈{SPY,IWM}, session==REGULAR, spot≥10, and all 7 indicators are merely *present* (`signal_engine.py:92-113`). It reads no EMA cross / MACD sign / RSI level / VWAP side for direction, and **always proposes BUY a CALL** (`:38-40,149-156`). It is structurally long-call-only and fires on every warm regular-session bar in-window. The engine is a delivery mechanism with no demonstrated edge — paper results will measure plumbing, not alpha.

**ROGUE-009 — Console ARM is cosmetic.** `set_arm`/`arm_state` only read/write the `ARM` file (`control.py:57-74`); nothing in `execution/` or `capital/` ever reads it. The *real* capital gate is the separate `CAPITAL_ARMED` env var via `capital_gate.py`. The console button implies an authorization it does not provide.

---

## 4. MEDIUM findings

**ROGUE-010 — Dead duplicate P&L accumulator.** `risk_engine.py` has `_DAILY_PNL_USD` + `record_realized_pnl` with its own hardcoded `MAX_DAILY_LOSS_USD=250` (`:36,44,176-190`), never called by the live path (the governor is). Confusing latent inconsistency.

**ROGUE-011 — Strike uses a stale spot.** Live `spot` is the last *completed* 1-min bar close (`market_data_ibkr_live.py:90-95`, `use_rth` default in `market_data_ibkr_history.py:55-65`); `strike = round(spot)` can be a tick off ATM in a fast open.

**ROGUE-012 — Connection multiplicity / clientId churn.** A singleton `IBKRRuntime` (orders+balance+quotes) plus a fresh `_HistClient` per `fetch_bars` (`market_data_ibkr_history.py:74-76,90`), each with a time-derived `clientId` (`ibkr_runtime.py:104`), opened every ~20s with no reuse/reconnection. Risks IBKR pacing/clientId issues over a session.

**ROGUE-013 — `clear_kill` is unauthenticated; kill file is plaintext/forgeable.** `control.py:41-52` + `kill_switch.py:133-147` unlink `/data/KILL` on a plain POST. Engage stays irreversible in-process (good), but the durable guarantee is only as strong as `/data` filesystem perms + the unauthenticated port.

**ROGUE-014 — CAPITAL balance source-semantics inconsistency.** The runtime writes `source="CAPITAL"` (`ibkr_runtime.py:339`), which preflight requires (`capital_preflight.py:146-147`), but the (dead) collector would write `source=execution_mode` ("PAPER"), which would fail that check if ever used.

**ROGUE-015 — Test suite is SIM-only; it masked the criticals.** 19/19 green, but every test is unit/SIM. Nothing exercises PAPER sizing or the live order/exit lifecycle — which is why ROGUE-001/002 shipped "green." This is the most important *process* gap.

---

## 5. LOW findings

- **ROGUE-016** — `LAW_VERSION_HASH = "LAW_V1_HASH_PLACEHOLDER"` baked into the seal (`execution_envelope.py:28`); LAW versioning is cosmetic.
- **ROGUE-017** — `Position.opened_at_utc` uses naive `utcnow()` (`execution_position_bridge.py:77`) vs tz-aware elsewhere; `held_seconds` works only because both ends are naive.
- **ROGUE-018** — Live balance snapshots store `snapshot_hash=None` (`ibkr_runtime.py:340`); audit-fidelity gap.
- **ROGUE-019** — Containers can reach host Ollama `:11434` (`docker-compose.yml`); advisory-only, low blast radius.

---

## 6. Dead code & architecture debt (~125 of 183 modules are off the live path)

Import-closure analysis (seeds: `run_paper_ibkr`, `terminal_server`, `market_loop`): **55 reachable.** The rest splits into legitimate research/tests and genuine dead scaffolding from retired architectures.

**ROGUE-020 — Retired subsystems, safe to delete (~2.5k LOC):** `arbitration/` (0/11 live), `strategy/` + `council/feedback/observation/context` (0/21), `audit/` (0/9, all the `*_audit_log` for the dead subsystems), `observation/` (0/5), `LAW/` + empty `laws/`, `sim_golden/`.

**ROGUE-021 — Dead advisory layer (several won't even import):** `option_selector`, `pricing_authority` (*it's a stale copy of an old `execution_driver.py`*), `option_qualifier`, `intent_authority` (hardcodes SYMBOL/ACTION), `qualified_contract`, `greeks_overlay`, `confidence_engine`, `parity_engine/harness`, and the per-indicator `ema/macd/atr/vwap/aavwap/level` authorities (the live engine computes inline).

**ROGUE-022 — Orphaned/broken modules calling nonexistent runtime methods (latent landmines):** `capital/ibkr_balance_collector.py:48` (`get_account_summary_blocking` — undefined), `broker/ibkr_option_discovery.py:110` (`request_contract_details` — undefined); plus unused `broker/ibkr_errors.py`, `capital/contract_cache.py`, `broker/ibkr_runtime_entrypoint.py`, dead `governance/{gcp_clients,law_parser,failure_manager,deterministic_runner,compliance_exporter}.py`, and the legacy `main.py` (GCP/Steady entrypoint, orphaned from the Docker path). `market/replay_*` are research-only — keep but isolate.

**ROGUE-023 — Stale/contradictory docs:** ~16 markdown files; several assert things now false (e.g., that PAPER sizing reads the store). Candidates to prune/refresh: `PHASE25_RECERT`, `PHASE3_SUMMARY`, `CAPITAL_GO_LIVE_AUTHORIZATION` (Mar), `ACTION_PLAN`, `EDGE_ROADMAP`, `CODEBASE_REVIEW` (superseded by this file).

---

## 7. Prioritized remediation roadmap

**P0 — make PAPER actually trade & close safely (do before trusting any paper result)**
ROGUE-001 (sizing → SQLite), ROGUE-002 (EXIT recovery), ROGUE-003 (cancel-on-timeout + reconnect). Add an integration test that drives a real PAPER entry→exit (closes ROGUE-015 for the happy path).

**P1 — required before any CAPITAL exposure**
ROGUE-004 (delete ws_server), ROGUE-005 (auth on /control/*), ROGUE-006 (partial fills), ROGUE-007 (entry reconciliation), ROGUE-013 (control auth), ROGUE-015 (PAPER/live lifecycle test coverage). **Independent of all this: there is still no edge (ROGUE-008)** — capital stays NO-GO on evidence grounds regardless of plumbing.

**P2 — hygiene & de-risking (reduce surface, stop the confusion)**
ROGUE-020/021/022 (delete dead code & landmines), ROGUE-010/014 (consolidate P&L + balance semantics), ROGUE-009 (make ARM real or remove it), ROGUE-011/012 (spot freshness + connection reuse), ROGUE-023 (docs), ROGUE-016/017/018/019.

---

## 8. Bottom line

The **chassis is well-engineered** — the safety envelope, kill, governor, and gate are the hard parts and they are right. But the **drivetrain is not connected**: PAPER can't size an order, can't safely close one, and abandons working orders on a timeout — and the "engine" has no directional logic. Tests are green because they only cover SIM. Fix P0 to get a trustworthy paper-forward; treat P1 as the bar for capital plumbing; and remember that none of it manufactures an edge, which remains the real gate (ROGUE-008).

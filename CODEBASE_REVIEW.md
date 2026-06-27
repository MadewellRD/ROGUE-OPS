# ROGUE:OPS — Full Codebase Review

> SDLC Command Desk · `workflow_run` (review/diagnostic) · 2026-06-27
> Connectors: filesystem + git (live), GitHub remote `MadewellRD/ROGUE-OPS` @ `37d7e83`.
> This is an audit pass, not a build pass — it runs the review/quality, test,
> security, and CI/release gates against the whole tree and produces a
> prioritized backlog. No code was changed.

## Source facts (measured this pass)

- 210 tracked files; **~18,200 Python LOC**.
- LOC by area: advisory 2.7k · tools 2.7k · execution 2.4k · market 1.8k ·
  governance 1.7k · broker 1.4k · capital 1.2k · strategy 1.1k · api 0.7k ·
  research 0.5k · audit 0.5k.
- Test suite: **16 tests** wired into `tools/run_all_tests.py`, gated by a git
  pre-push hook (last push: 16/16 green).
- `0` TODO/FIXME/XXX/HACK markers in `*.py`.
- Recent arc: console → shadow advisor → shadow eval → Docker always-up →
  GCP-free paper loop on IBKR.

## Workflow scope

| Stage | Run? | Note |
|---|---|---|
| Technical discovery | ✅ | inventory + dependency/dead-code scan |
| Architecture/design | ✅ | boundaries, half-finished migration |
| Review/quality | ✅ | tests, orphans, dead code |
| Test/verification | ✅ | coverage gaps, regression integrity |
| Security/threat | ✅ | secret-in-history, exec surface |
| CI/release readiness | ✅ | local-only enforcement, versioning |
| Maintenance/refactor | ✅ | prioritized backlog (below) |
| Implementation handoff | ⏸ | gated — see Workflow Halt |

---

## What's strong (keep)

The spine is genuinely well-built and I want to be clear about that before the findings:

- **Deterministic, fail-closed execution.** Envelope-sealed orders, a kill switch that is now durable + cross-process (file-backed, honored on boot), capital gates, and a single daily-loss PnL source of truth.
- **Clean layering.** `governance / execution / capital / broker / market / advisory / research / api` separate cleanly; the multi-broker boundary routes by capability and fails closed on `BROKER_UNSUPPORTED`.
- **Test-guarded.** 16 isolated-subprocess tests with a pre-push gate that has repeatedly caught real regressions, including a mechanical guard that `execution/` and `capital/` never import the LLM advisory layer.
- **Honest research.** The backtest/shadow apparatus reports breakeven-to-negative results plainly rather than curve-fitting a fake edge.

---

## Findings (severity-tagged, with evidence)

### P0 — do before anything touches capital or stays public

**S1. SteadyAPI key in git history — NEUTRALIZED.** The SteadyAPI account is now **dead** (owner-confirmed), so the historical key is inert and the security exposure is closed. The Steady code paths have been removed entirely (see *Cleanup applied*). History scrub is now optional hygiene, not a security action.

### P1 — correctness, integrity, and hygiene (soon)

**A1. Half-finished Steady → IBKR migration; two divergent PAPER paths.** Steady is still woven through `execution/intent_router.py`, `execution/paper_trade_driver.py`, `market/market_data_loop.py`, and `main.py`'s PAPER branch — while the new `tools/run_paper_ibkr.py` deliberately *bypasses* `main.py` to run GCP-free on the IBKR feed. Two paper entrypoints with different data sources and bootstrap requirements is a maintenance and correctness hazard.
*Action:* pick the IBKR path as canonical; fold it into `main.py` (or formally designate `run_paper_ibkr.py` as the entrypoint and deprecate the `main.py` PAPER branch); delete the Steady execution paths once nothing imports them.

**A2. `main.py` PAPER is GCP-coupled.** The non-SIM branch hard-requires `GCP_PROJECT_ID`, `DOCTRINE_BUCKET`, and Google credentials and loads doctrine/secrets from GCS — at odds with the stated Massive-+-IBKR direction. Resolve as part of A1 (load doctrine locally or drop it for the IBKR path).

**T1. Orphan tests not in the runner.** `tools/test_engine_and_execution.py` is tracked but **absent from `run_all_tests.py`**, and a legacy `test_quotes.py` sits at repo root (Steady-era). "16/16 green" therefore does not mean "all tests ran." *Action:* wire `test_engine_and_execution` into the runner or delete it; remove/retire `test_quotes.py`.

**V1. SIM regression determinism — VERIFIED OK (finding withdrawn).** On reading `run_sim_regression.py`, the gate *does* enforce determinism: it asserts `indicator_assertion_hash` and `execution_status` against the golden record. The `parity_hash`/`envelope_hash` printed as "(volatile)" are intentionally observed-not-compared because they embed timestamps. No action needed.

**C1. CI is local-only and bypassable.** `.github/workflows/ci.yml` exists but is **untracked/unpushed** (OAuth lacks `workflow` scope), and the pre-push hook can be skipped with `--no-verify`. *Status:* owner restoring the paid GitHub plan **next week**, at which point the workflow goes live server-side. Time-gated, not blocked.

### P2 — improvements / debt reduction

**M1. Dead and vestigial code.** `broker/ibkr_client.py` has **no importers** (superseded by `ibkr_runtime.py`). The `strategy/` subsystem (~1.1k LOC: registry/feedback/council) was superseded by the SignalEngine path in Phase 3 yet is still bootstrapped in `main.py`. The Robinhood MCP client remains a scaffold (transport TODO). *Action:* delete `ibkr_client.py`; quarantine or remove `strategy/` if truly unused; mark Robinhood explicitly deferred.

**Q1. Coverage is breadth-light in the riskiest module.** `execution/` is the largest non-tooling area (2.4k LOC) but deep router/state-machine branches are only indirectly exercised. No coverage measurement exists. *Action:* add `coverage.py` to the runner and backfill execution-router/state-machine edge cases.

**R1. No release discipline.** No tags, versioning, CHANGELOG, or release notes. For a system you'll gate capital on, a versioned, signed release boundary is worth having. *Action:* adopt lightweight semver tags + a CHANGELOG, tag the pre-capital baseline.

---

## Cleanup applied (2026-06-27, same pass)

Owner directed: make `run_paper_ibkr.py` canonical and strip Steady; keep
`strategy/`. Executed, suite-gated:

- **Deleted the dead Steady chain + dead modules** (all had zero live importers):
  `broker/ibkr_client.py`, `market/market_data_loop.py`, `execution/intent_router.py`,
  `market/multi_symbol_orchestrator.py`, `execution/paper_trade_driver.py`,
  `advisory/uncertainty.py`, `market/market_data_adapter_steady.py`,
  `governance/api_clients.py`.
- **Removed stale/orphan tests:** `tools/test_engine_and_execution.py` (imported a
  non-existent `rogueops.*` package) and root `test_quotes.py` (Steady-era).
- **`main.py`** rewritten GCP-free + Steady-free: SIM/REPLAY self-test only;
  PAPER/LIVE point to `tools/run_paper_ibkr.py`. (Resolves A1 + A2.)
- **`market_loop.run_market_loop`** now requires an injected `snapshot_provider`
  and fails closed (engages kill) without one; the lazy Steady import is gone.
- **Kept** (owner decision / conservative): `strategy/` and `governance/gcp_clients.py`
  (now unreferenced but retained as infra, like `strategy/`).

Net: ~10 files removed; S1 closed; A1/A2/T1/M1(ibkr_client) resolved.

## Decisions taken this pass

- Treated git/filesystem as authoritative for repo state; GitHub remote confirmed at `37d7e83`.
- Classified the request as a cross-cutting audit (not a single-desk artifact), so multiple gates were run and synthesized rather than routing to one desk.
- Did **not** modify code or rotate secrets — those are owner actions (S1) or need decisions (A1).

## Open questions

1. Is the `strategy/` subsystem intended to return, or is it dead weight to remove?
2. Is SIM determinism still a guarantee (V1), or is the regression now a smoke test?
3. Keep `main.py` PAPER at all, or make `run_paper_ibkr.py` the sole paper entrypoint (A1)?

## Workflow Halt — implementation handoff gated

Implementation handoff is **not** produced this pass. Blockers and exact resume requirements:

- **S1 (secret)**: owner must rotate + decide on history scrub — I will not handle the brokerage/vendor credential or rewrite published history without explicit confirmation.
- **C1 (CI)**: pushing `.github/workflows/ci.yml` needs a workflow-scoped token or the GitHub UI — current auth lacks `workflow` scope.
- **Live paper verification**: the new IBKR live-data adapter is pure-tested only; verifying it end-to-end needs `docker` execute access (pending) **and** IB Gateway up (owner).
- **Edge**: Phase 9 (capital) stays gated — research shows no validated edge.

## Workflow packet

```yaml
mode: workflow_run
completed_stages: [technical_discovery, architecture, review_quality, test_verification, security_threat, ci_release_readiness, maintenance_refactor]
next_stage: implementation_handoff
source_facts:
  repo: MadewellRD/ROGUE-OPS@37d7e83
  loc_python: ~18200
  tracked_files: 210
  tests_in_runner: 16
  orphan_tests: [tools/test_engine_and_execution.py, test_quotes.py]
  dead_code: [broker/ibkr_client.py, strategy/* (vestigial), broker/robinhood_mcp.py (scaffold)]
  steady_refs: [execution/intent_router.py, execution/paper_trade_driver.py, market/market_data_loop.py, main.py, governance/api_clients.py]
  ci_workflow_pushed: false
decisions: [audit-not-build, git-authoritative, no-code-change]
open_questions: [strategy-subsystem-fate, sim-determinism-intent, single-paper-entrypoint]
halt_conditions: [S1-secret-owner, C1-workflow-scope, live-paper-needs-docker+gateway, edge-unproven]
ready_to_continue: false
resume_when: "owner confirms A1 direction (single paper path) and authorizes the P0/P1 cleanup; then route to maintenance-refactor → implementation-handoff for the Steady-removal + dead-code + test-wiring changes."
```

## Recommended next action (sequenced)

1. **You:** rotate the Steady key (S1); add the CI workflow via GitHub UI (C1).
2. **Me, on your go:** a focused cleanup PR — remove `ibkr_client.py`, wire/retire the orphan tests (T1), make `run_paper_ibkr.py` canonical and strip the Steady execution paths (A1/A2), confirm the SIM determinism gate (V1). All behind the 16-test suite + hook.
3. **Deferred (gated):** `strategy/` removal pending your call (Q1); live paper verification pending docker access + Gateway; capital pending a proven edge.

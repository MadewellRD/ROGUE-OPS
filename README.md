# ROGUE:OPS — Retail Options Gamma Utility Engine

A safety-first, deterministic **autonomous trading engine** for US index options
(SPY / IWM, 0DTE) — built as an execution + research platform. Every order flows
through an immutable, hashed, kill-dominant, fail-closed `ExecutionEnvelope`.

> ⚠️ **Not financial advice. No warranty. Not a money-maker.**
> Trading options can lose your entire capital. This system has **no demonstrated
> trading edge** — that was tested on real data and confirmed negative (see
> [`EDGE_ROADMAP.md`](EDGE_ROADMAP.md)). It is published as an **engineering +
> research showcase**, for education only. By the project's own evidence,
> real-money deployment is **NO-GO**. Use entirely at your own risk.

---

## Why this repo is worth reading

The interesting part isn't a strategy — it's the discipline:

1. **A production-grade safety envelope for autonomous options trading** — cross-process
   kill switch, operator ARM gate, daily-loss governor from real fills, sealed/dual-hashed
   execution envelopes, capability-routed multi-broker boundary, marketable-limit-or-refuse
   pricing, safe no-fill/partial-fill recovery, and an IBKR reconnect watchdog. All
   fail-closed, all covered by tests.
2. **A full, honest edge investigation** — three independent strategy families backtested on
   real option + equity data, walk-forward out-of-sample, **all negative** — and the
   engineering judgment to say *no* to capital rather than deploy a proven loser.

Build it well, then prove the negative cleanly. That's the project.

## Architecture (live path)

```
IBKR live bars ─▶ IndicatorEngine ─▶ SignalEngine ─▶ StateMachine ─▶ ExecutionEnvelope ─▶ broker ─▶ IBKR (options)
  (market/)        (advisory/)        (advisory/)     (execution/)     (sealed + hashed)   (broker/)   marketable-limit
                 EMA·RSI·MACD·ATR·VWAP  entry signal   arm/risk/time/capital gates                     or refuse
```

Open positions are managed and exited before any new entry (*exit supremacy*). Nothing
trades without a sealed `ExecutionEnvelope`.

## Safety model (fail-closed by design)

- **Kill switch** — durable + cross-process (a file under `ROGUE_OPS_HOME`), irreversible per
  run, re-checked at every authority boundary; the console KILL button halts the loop.
- **ARM gate** — PAPER/CAPITAL entries require an explicit operator ARM; SIM is exempt.
- **Daily-loss governor** — accrues realized P&L from *actual fills*; engages the kill on
  breach (default `$250`) and blocks further entries.
- **Sealed envelopes** — every order is an immutable, dual-SHA-256 `ExecutionEnvelope`,
  verified before any broker contact.
- **Safe order lifecycle** — options priced off live NBBO as a marketable limit (naked market
  orders refused unless explicitly forced); no-fill exits recover instead of stranding;
  timed-out orders are cancelled; a reconnect watchdog restores a dropped IBKR session.
- **Capital gate** — real-money mode requires explicit `CAPITAL_ARMED` + a passing preflight;
  layered and fail-closed.

## The honest edge verdict

The machine is sound; the strategy is not. Tested on real data, walk-forward out-of-sample:

| Strategy family | Result |
|---|---|
| 0DTE directional (long calls/puts, trend/breadth) | no edge |
| 0DTE iron condor (5 configs, 55 expiries, real option prices) | no edge, degrades OOS |
| Momentum + top-10 breadth vs 1/3/5/7-day forward returns (SPY/QQQ/IWM) | OOS corr ≈ 0 |

No signal tested predicts returns, so no DTE/symbol/structure choice makes money — the
efficient-market result. Full reasoning in [`EDGE_ROADMAP.md`](EDGE_ROADMAP.md); a complete
codebase audit in [`CODEBASE_AUDIT.md`](CODEBASE_AUDIT.md); remediation log in
[`REMEDIATION_TRACKER.md`](REMEDIATION_TRACKER.md).

## Repo layout

| Path | Purpose |
|------|---------|
| `market/` | IBKR live snapshot feed, `MarketSnapshot`, the `market_loop` |
| `advisory/` | rolling `IndicatorEngine` (EMA/RSI/MACD/ATR/VWAP) + `SignalEngine` + optional Ollama shadow advisor |
| `execution/` | state machine, sealed envelope, router, position store/bridge, exit engine, position sizing |
| `broker/` | `BrokerRuntime` boundary + IBKR runtime/broker + pricing (+ Robinhood MCP for equities) |
| `capital/` | balance store, daily-loss governor, capital gate/preflight, trade ledger + scorecard |
| `governance/` | kill switch, arm switch, risk engine, ops state, paths, audit store, bootstrap |
| `api/` | operator console (`terminal_server.py`, `terminal_state.py`, `console.html`) |
| `research/` | backtest harness, strategy candidates, intraday study, options backtest, forward-return study |
| `tools/` | 23-test suite (`run_all_tests.py`), paper entrypoint (`run_paper_ibkr.py`), probes |

## Quickstart

### SIM + tests (no broker, no cloud)

```bash
python tools/run_all_tests.py      # 23 tests, each in an isolated process
```

### Paper trading (Dockerized, IBKR feed)

Requires IB Gateway (paper, port `4002`, API enabled, paper disclaimer accepted).

```bash
docker compose --profile paper up -d --build
# operator console: http://127.0.0.1:8787   (loopback only)
```

See [`DOCKER.md`](DOCKER.md). The loop starts **disarmed** — it will not enter until you ARM
it from the console; the daily-loss kill and all gates remain in force.

## Configuration (env)

| Env | Purpose |
|-----|---------|
| `EXECUTION_MODE` | `SIM` / `PAPER` / `CAPITAL` |
| `ROGUE_OPS_HOME` | runtime data/audit root (cross-platform) |
| `IBKR_HOST` / `IBKR_PORT` | Gateway socket (paper `4002`) |
| `MAX_DAILY_LOSS_USD` | daily realized-loss kill threshold (default `250`) |
| `OPS_KILL_SWITCH` | `true` to force kill at startup |
| `OLLAMA_SHADOW` | `1` to enable the advisory-only, execution-isolated LLM shadow read |

## Security / operating notes

- Secrets live in **gitignored** `.env` / `.massive_key` — never committed (verified: no keys
  in tree or history).
- The operator console binds **loopback only** (`127.0.0.1:8787`) and is **unauthenticated** —
  do not expose it to a network.
- `.roguedata/` (balances, trade ledger, kill file, audit) is gitignored and operator-local.

## License

**AGPL-3.0.** Network/SaaS use requires source disclosure. See [`LICENSE`](LICENSE).

## Disclaimer

Trading options carries a substantial risk of **total loss** and is not suitable for every
investor. This software is provided **as-is**, with **no warranty**, and is **not financial
advice**. It has **no proven edge** (proven negative in this repo). Any use — paper or live —
and all of its consequences are solely your responsibility.

# ROGUE:OPS — Retail Options Gamma Utility Engine

A deterministic, kill-dominant automated trading system for US index options
(SPY / IWM, 0DTE). It turns market data into risk-gated, envelope-sealed orders
across a multi-broker boundary, with safety controls that fail closed.

> **Status:** SIM-verified and **paper-verified on IBKR** (live equity + 0DTE
> option fills with real fill capture). Guarded by an automated test suite.
> **Not cleared for live capital** — see [Go-live gates](#go-live-gates).

---

## What it does

```
market snapshot ──▶ indicators ──▶ SignalEngine ──▶ StateMachine ──▶ ExecutionEnvelope ──▶ broker boundary ──▶ IBKR / Robinhood
   (market/)        (advisory/)     (advisory/)      (execution/)        (sealed)            (broker/)
                  VWAP·ATR·RSI·     entry signal     authorize +                          options→IBKR
                  EMA·MACD                           risk/time/capital gates              equities→Robinhood
```

The live decision path is **market → indicators → SignalEngine → state machine →
execution → broker**. Open positions are managed and exited before any new entry
(*exit supremacy*). Every execution flows through an immutable, sealed
`ExecutionEnvelope`; nothing trades without one.

## Safety model (fail-closed by design)

- **Kill switch** — process-dominant and irreversible per run; checked at envelope creation, the execution router, and the state machine.
- **Daily-loss governor** — accrues realized P&L from *actual fills*; on breach it engages the kill and blocks further entries.
- **Marketable-limit pricing** — 0DTE options are priced off the live NBBO; if no quote is available the order is **refused** rather than sent as a naked market order.
- **Capability-routed brokers** — options route to IBKR, equities to Robinhood; routing an instrument to a broker that can't trade it is blocked (`BROKER_UNSUPPORTED`).
- **Hard mode gates** — `LIVE`/`CAPITAL` require explicit env and pass startup gates; SIM/REPLAY are fully self-contained.

## Repo layout

| Path | Purpose |
|------|---------|
| `main.py`, `ops_config.py` | entrypoint + immutable runtime config / mode gating |
| `market/` | SteadyAPI data adapter, `MarketSnapshot`, the live `market_loop` |
| `advisory/` | rolling `IndicatorEngine` (VWAP/ATR/RSI/EMA/MACD) + `SignalEngine` |
| `execution/` | state machine, sealed envelope, router, position store/bridge, exit engine, sizing |
| `broker/` | `BrokerRuntime` boundary + IBKR adapter + Robinhood MCP adapter + pricing |
| `capital/` | balance store, daily-loss governor, capital gate, preflight |
| `governance/` | kill switch, risk engine, ops state, cross-platform paths, audit store |
| `api/` | operator terminal (`terminal_server.py`, `terminal_state.py`, `terminal.html`) |
| `tools/` | test suite, `run_all_tests.py`, IBKR/Robinhood smoke + probe tools |
| `sim_golden/` | deterministic SIM golden record |
| `arbitration/`, `strategy/` | legacy council/arbitration scaffolding — **not on the live path** |

## Quickstart — SIM (no broker, no cloud)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-sim.txt

$env:OPS_MODE="SIM"; $env:OPS_ENV="DEV"; $env:OPS_VERSION="0.0.0-sim"; $env:EXECUTION_MODE="SIM"
python main.py --mode SIM
```

Full details in [`SIM_RUNBOOK.md`](SIM_RUNBOOK.md).

## Tests

```powershell
python tools\run_all_tests.py
```

Runs pricing, broker routing, indicators, the full market-loop lifecycle, the
safety governor, fill→P&L→kill, and the SIM regression — each in an isolated
process. CI runs the same suite on every push via `.github/workflows/ci.yml`.

## Operator terminal

```powershell
python -m api.terminal_server      # → http://localhost:8787
```

A local, read-only dashboard: capital, daily-loss risk, open position, SPY/IWM
price + VWAP, the indicator stack, signal state, broker routing, and kill status.
Details in [`TERMINAL.md`](TERMINAL.md).

## Brokers

- **IBKR (options + equities)** — requires TWS or IB Gateway running, API enabled, socket port `7497` (paper). Live option pricing needs the real-time OPRA market-data subscription. Paper verification: `python tools\ibkr_paper_smoke.py`.
- **Robinhood (equities, beta)** — connects to Robinhood's Agentic Trading MCP via a headless client + one-time OAuth. Setup in [`ROBINHOOD_SETUP.md`](ROBINHOOD_SETUP.md).

Backend selection: `BROKER=IBKR|ROBINHOOD` (or capability default); equity broker via `EQUITY_BROKER`.

## Configuration

| Env | Purpose |
|-----|---------|
| `OPS_MODE` / `OPS_ENV` / `OPS_VERSION` | runtime identity (SIM/REPLAY/PAPER/LIVE) |
| `EXECUTION_MODE` | `SIM` / `PAPER` / `CAPITAL` |
| `ROGUE_OPS_HOME` | runtime data/audit root (cross-platform; default per-OS) |
| `IBKR_HOST` / `IBKR_PORT` | TWS/Gateway socket (default `127.0.0.1:7497`) |
| `MAX_DAILY_LOSS_USD` | daily realized-loss kill threshold (default 250) |
| `OPS_KILL_SWITCH` | `true` to force kill at startup |

## Go-live gates

The system is **not** cleared for live capital until:

1. [`PHASE25_RECERT.md`](PHASE25_RECERT.md) is signed (execution-path re-certification).
2. The IBKR **OPRA real-time options data** subscription is active (so option pricing runs without overrides).
3. Robinhood OAuth token is provisioned (for the equities path).

See [`ACTION_PLAN.md`](ACTION_PLAN.md) for the full assessment and roadmap, and
[`PHASE3_SUMMARY.md`](PHASE3_SUMMARY.md) for the hardening record.

## Disclaimer

Trading options carries a substantial risk of loss and is not suitable for every
investor. This is software provided **as-is**, with no warranty, and is **not
financial advice**. Validate everything in paper/SIM; any live use and its
consequences are solely your responsibility.

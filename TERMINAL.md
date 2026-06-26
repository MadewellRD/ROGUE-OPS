# ROGUE:OPS — Operator Terminal

A dense, Bloomberg-style operator dashboard for the trading system. Dependency-free
(Python stdlib + Chart.js from CDN). Shows live execution mode, kill-switch status,
capital, daily-loss risk, the open option position, SPY/IWM price with VWAP,
the indicator stack (RSI/EMA/MACD/ATR/VWAP), signal state, and broker routing.

## Run

```powershell
# from repo root
python -m api.terminal_server
# -> open http://localhost:8787
```

- **Standalone**: shows current durable state (kill switch, daily-loss governor, last balance snapshot, open position).
- **Alongside the market loop** (PAPER/LIVE/CAPITAL): the loop publishes a live frame each cycle, so market price, indicators, and signal state update in real time.
- **Offline / no data**: the UI falls back to an animated **demo feed** and clearly labels itself `DEMO DATA`, so it always renders.

## Panels

| Panel | Source |
|------|--------|
| Capital (NetLiq / BuyingPower / Available / Excess) | `capital/balance_store` (IBKR account stream) |
| Risk · Daily Loss Governor (realized P&L vs limit, breach) | `capital/daily_loss_governor` |
| Position (open option, entry, qty) | `execution/position_store` |
| Market (spot + VWAP chart) | market loop frame |
| Indicators (VWAP/ATR/RSI/EMA/MACD, `required` gate) | market loop frame |
| Signal (ENTRY / EXIT / HOLD / NO_SIGNAL / …) | `market_step` status |
| Broker Routing (options→IBKR, equities→Robinhood, fail-closed) | `broker/broker_runtime` config |
| Kill / Mode / Session (top bar) | `governance/kill_switch`, env, session |

## Architecture

```
market loop --publish_frame()--> api/terminal_state (in-memory aggregator)
                                         |
   browser <-- GET /state (JSON) -- api/terminal_server (stdlib HTTP) -- get_terminal_state()
   browser <-- GET /     (UI)    -- api/terminal.html (polls /state every 1s)
```

The terminal is **read-only** — it never places orders or mutates state. It reads
the same authorities the engine uses, so what you see is what the system sees.

## Config

| Env | Default | Meaning |
|-----|---------|---------|
| `TERMINAL_PORT` | `8787` | HTTP port |
| `ROGUE_BALANCE_ACCOUNT` | `IBKR` | account id whose balance snapshot to show |

## Notes / next

- Capital populates only when the IBKR balance stream is active (TWS up, PAPER/CAPITAL).
- Live P&L on the open position is entry-only today; exact mark-to-market arrives with the IBKR `avgFillPrice` fill-capture work.
- The server binds `127.0.0.1` (localhost only). Keep it that way — it exposes account state.

# Public Trading-Repo Landscape — and where ROGUE:OPS sits

> Snapshot: 2026-06-27. Star counts are approximate and move; GitHub's API
> wasn't reachable from this environment, so figures are web-sourced and rounded.
> Treat as positioning, not a leaderboard.

## The field, by category

### 1. Mature general frameworks (the "big" repos)
These are broad, multi-asset, years-deep, large communities. ROGUE:OPS is **not**
competing here and shouldn't pretend to.

| Repo | ~Stars | Focus |
|---|---:|---|
| `freqtrade/freqtrade` | ~50k | Crypto bot; ML via FreqAI; huge strategy community |
| `backtrader/backtrader` | ~22k | Backtesting engine (now largely inactive) |
| `QuantConnect/Lean` | ~19k | Full algo engine; real options multi-leg, IV/Greeks |
| `hummingbot/hummingbot` | ~19k | Market-making / crypto |
| `jesse-ai/jesse` | ~8k | Crypto bot + clean backtester |
| also: `ccxt`, `zipline-reloaded`, `vnpy`, `nautilus_trader`, `OctoBot`, `StockSharp` | — | exchange APIs, engines, HFT-grade |

Takeaway: these win on breadth, data integrations, backtesting at scale, and
community. None of them *promise an edge* — they're toolkits.

### 2. Interactive Brokers ecosystem (your execution layer)
| Repo | ~Stars | Focus |
|---|---:|---|
| `erdewit/ib_insync` | ~2.8k | The classic IBKR wrapper (now archived) |
| `ib-api-reloaded/ib_async` | ~1.6k | Maintained successor (active Jun 2026) — **worth migrating to** |
| `9600dev/mmr` | — | IBKR platform "operated by both humans **and LLMs**" |
| `Roro253/ibkr-ai-trading-bot` | — | IBKR options bot: XGBoost + VWAP/MACD/RSI, GUI, backtest |
| `ldt9/PyOptionTrader`, `jamesmawm/HFT-Model-with-IB` | — | options / HFT on IBKR |

Note: ROGUE:OPS talks to IBKR via the official `ibapi`. `ib_async` is the
community-preferred, higher-level wrapper — a possible future simplification.

### 3. Options / 0DTE-specific (your lane)
| Repo | Focus | Note |
|---|---|---|
| `IgorGanapolsky/trading` | **Paper-first SPY options, hard risk gates, broker-backed scorecards, paired-trade accounting, live dashboards** | The closest sibling to ROGUE:OPS in *philosophy* |
| `pattertj/LoopTrader` | Extensible options bot (TastyTrade/TDA lineage) | Established |
| "TrueLiesBot" / various 0DTE bots | SPY/QQQ 0DTE, 3-indicator confirmation, advertised "8,840% return" | The hype archetype ROGUE:OPS deliberately rejects |
| `ilcardella/TradingBot` | Autonomous stock trading | General |

Takeaway: the 0DTE space is thick with **return claims** (57% win, thousands of
percent) that are almost always overfit, look-ahead-biased, or cherry-picked.

### 4. LLM / agentic trading (the new wave, 2025–26)
| Repo | Focus |
|---|---|
| `TauricResearch/TradingAgents` | Flagship multi-agent LLM framework (LangGraph): analyst/sentiment/technical agents debate |
| `pipiku915/FinMem-LLM-StockTrading` | Memory-augmented LLM agent |
| `EthanAlgoX/LLM-TradeBot` | Judges "**IF** we should trade" before "HOW" — same instinct as ROGUE's presence-gate |
| `HKUDS/Vibe-Trading` | Personal LLM trading agent; tracks token usage |
| `qrak/LLM_trader` | Vision-AI chart reading + post-trade reflection |

Takeaway: this wave puts the LLM **inside the decision loop**. That's the bet
ROGUE:OPS explicitly declines.

---

## How ROGUE:OPS stacks up

**Where it's genuinely differentiated (top decile, honestly):**

1. **Safety/determinism as the headline, not an afterthought.** Envelope-sealed
   orders, fail-closed everything, a cross-process durable kill, a single-source
   daily-loss governor, capital gated behind a signed re-cert. Almost every
   public bot leads with *strategy*; a handful (notably `IgorGanapolsky/trading`)
   lead with *risk discipline*. ROGUE:OPS is firmly in that rare camp.
2. **Intellectual honesty about edge.** ROGUE:OPS states plainly it has **no
   proven edge** and gates capital on evidence. The 0DTE/LLM corner of GitHub is
   full of unverifiable return claims. Saying "breakeven-to-negative, staying on
   paper" is rarer — and more credible — than any "8,840%".
3. **LLM kept *out* of the execution path.** While TradingAgents/FinMem put the
   model in the loop, ROGUE:OPS runs the LLM as a **logged shadow advisor,
   measured against the deterministic engine before it is ever trusted** — with a
   test that mechanically forbids `execution/` from importing it. That's a more
   defensible posture than the agentic-LLM repos.
4. **Test-guarded + CI gate.** A 16-test suite with a pre-push hook that has
   caught real regressions. The mature frameworks are well-tested; the
   hobby 0DTE/LLM bots usually aren't.
5. **Clean multi-broker boundary** (IBKR options + Robinhood equities, capability
   routing, fail-closed `BROKER_UNSUPPORTED`) — tighter than typical single-broker
   scripts.

**Where it's behind (also honestly):**

1. **No proven edge** — the one that matters. (Caveat: neither do most of the
   bots claiming otherwise; the difference is ROGUE:OPS admits it.)
2. **Strategy & backtest breadth** — Lean/freqtrade have years of strategies,
   vectorized multi-asset backtesting, parameter optimization, and live track
   records. ROGUE:OPS has a bespoke, small harness and a handful of candidates.
3. **Data** — currently daily-tier Massive + IBKR bars; the frameworks integrate
   many feeds, and real 0DTE edge likely needs options IV/flow data ROGUE doesn't
   have yet.
4. **Scope & community** — SPY/IWM 0DTE only, single operator. The big repos are
   broad and have thousands of contributors.

**Closest siblings:** `IgorGanapolsky/trading` (paper-first + gates + dashboards),
`Roro253/ibkr-ai-trading-bot` (IBKR options + indicators + GUI + backtest),
`9600dev/mmr` (human-and-LLM-operated IBKR platform).

---

## The verdict (director-level)

ROGUE:OPS isn't a freqtrade/Lean competitor — it's a **personal, safety-obsessed,
single-purpose 0DTE engine** whose moat is *operational discipline and honesty*,
not breadth or advertised returns. Against the mature frameworks it's small and
early; against the hobby 0DTE/LLM bots it's far more rigorous on safety, testing,
and honesty — but, like them, it has no validated edge.

The strategic point worth internalizing: **almost nobody public has a verified,
durable 0DTE edge.** The repos shouting huge returns are the red flags, not the
benchmark. So ROGUE:OPS is "ahead" on exactly the axis that's cheap to fake
(discipline, safety, honesty) and "even with the field" on the axis that's hard
and rare (edge). That's the right place to be *before* the data upgrade — it means
the machine is trustworthy and the only missing ingredient is the one piece no
amount of engineering can fake.

Two concrete borrowings worth considering:
- **`ib_async`** as a future replacement for raw `ibapi` (cleaner, maintained).
- **Scorecard/paired-trade accounting** like `IgorGanapolsky/trading` — a natural
  extension of the shadow ledger + go-live gate.

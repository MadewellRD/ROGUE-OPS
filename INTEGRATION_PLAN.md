# Integration Deep-Dive: `ib_async` + Scorecard / Paired-Trade Accounting

> 2026-06-27. Two borrowings from the landscape scan, with file-level plans,
> effort, risk, and a sequenced recommendation. Bottom line up front:
> **build the scorecard now; defer the `ib_async` migration until after the edge gate.**

---

## 1. `ib_async` — replace the hand-rolled `ibapi` plumbing

### What it is
`ib-api-reloaded/ib_async` (the maintained successor to `erdewit/ib_insync`,
~1.6k★, active Jun 2026) is a high-level wrapper over IBKR's TWS API. It collapses
the raw `ibapi` callback/threading/reqId model into direct calls that return
results and rich objects (`Trade` with `.orderStatus`, `.fills`, `.avgFillPrice`).

### Current ROGUE footprint (what we'd be replacing)
| File | What it hand-rolls today |
|---|---|
| `broker/ibkr_runtime.py` (~360 LOC) | `EWrapper/EClient`, connect, `nextValidId`, `orderStatus`/fills capture, `wait_for_fill`, `fill_price`, `get_quote` (NBBO snapshot), reqId mgmt, the `_RUNTIME` singleton |
| `broker/ibkr_broker.py` | contract build, MKT / marketable-limit, `eTradeOnly=False`, place + wait-for-fill |
| `market/market_data_ibkr_history.py` | `_HistClient` + `fetch_bars` (reqHistoricalData via threads + `Event`s) |
| `market/market_data_ibkr_live.py` | provider over `fetch_bars` |

### Migration map
| Today (raw `ibapi`) | `ib_async` equivalent |
|---|---|
| `_HistClient` + threaded `fetch_bars` + `Event`s | `ib.reqHistoricalData(contract, '', '1 D', '1 min', 'TRADES', useRTH=True)` → returns bars directly |
| `get_quote()` NBBO snapshot via `reqMktData` ticks | `t = ib.reqMktData(contract); ib.sleep(1); t.bid/t.ask/t.last` |
| `next_order_id` + `orderStatus`/`_order_fills` + `wait_for_fill` + `fill_price` | `trade = ib.placeOrder(c, o)`; `trade.orderStatus.status`, `trade.orderStatus.avgFillPrice`, `trade.fills` (built-in) |
| manual `Contract()` assembly | `Stock('SPY','SMART','USD')`, `Option(sym,exp,strike,right,'SMART')`, `ib.qualifyContracts()` |

### Benefits
- Deletes ~300+ LOC of threading/reqId/`Event`/callback glue → fewer concurrency bugs.
- `avgFillPrice` + fills + order status come **for free** (we hand-roll these today).
- Built-in reconnect (`ib.connectedEvent`), contract qualification, pacing-aware historical.

### Risks (why this is not a casual swap)
- **New dependency** (`ib_async` pulls `eventkit` + `nest_asyncio`, uses `asyncio`). ROGUE is sync/threaded; `ib_async` supports sync use (`ib.sleep`/`ib.run`) but the loop's 1s-cadence model needs a clean event-loop story.
- Must **preserve**: fail-closed semantics, marketable-limit pricing (`broker/pricing.py`), the `eTradeOnly=False/firmQuoteOnly=False` compat fix, the `BrokerRuntime` Protocol contract, and the *verified* paper behavior.
- It's a refactor of the **certified** IBKR order path → requires re-verification + re-cert.

### Low-risk integration approach (when we do it)
ROGUE already has the seam: `broker/broker_runtime.py` (Protocol) + `get_broker_runtime()` factory. So:
1. Add a **second** implementation `broker/ibkr_async_broker.py` behind a flag `IBKR_CLIENT=ibapi|ib_async` (default `ibapi` = proven). Factory picks.
2. Migrate the **data feed first** (read-only, lowest risk): an `ib_async`-backed `fetch_bars`; verify bars match the `ibapi` path against paper.
3. Then execution; keep the `ibapi` path as fallback until the async path is paper-verified + re-cert'd.
4. `Dockerfile.paper`: add `pip install ib_async` (it would supersede `ibapi`).

**Effort:** data feed ~0.5 day; execution ~1–2 days + re-verify.
**Recommendation: DEFER.** It adds zero edge and touches the one path that's already
certified and working (78 live bars, paper fills). Do it post-edge, or in a
maintenance window — never right before the go-live gate.

---

## 2. Scorecard / paired-trade accounting — from `IgorGanapolsky/trading`

### What they do (and why it's the closest sibling)
That repo is a paper-first SPY-options platform with: an LLM (Claude Opus) **in**
the decision loop, a LanceDB RAG "lessons" memory, **paired-trade accounting**, a
**scorecard**, and a unified **`TradeGateway`** enforcing hard pre-broker gates
(lot cap, IV-rank floor, daily-loss + drawdown circuit breakers, position-count
cap, illiquid-option rejection, FOMC blackout, lesson-blocks). Tellingly, they
**retracted a "60% Thursday win-rate" edge** when it failed statistical
correction — the same rigor ROGUE applies.

Two things worth borrowing: **(a) the scorecard/paired-trade ledger** (now), and
**(b) the unified `TradeGateway`** (later, needs options data).

### (a) Scorecard / paired-trade ledger — the clean hook
`execution_position_bridge.handle_exit()` **already** has the full closed trade at
exit — entry (symbol/strike/right/action/qty/entry_price/opened_at), exit price,
and realized P&L — but currently returns only `{"realized_pnl_usd": ...}`. So the
integration is small and surgical:

1. **`execution/execution_position_bridge.py`** — extend `handle_exit`'s return to
   the full paired record (add entry/exit/qty/side/strike/right/held_seconds +
   the existing realized P&L). No behavior change.
2. **`capital/trade_ledger.py`** (new) — paired-trade accounting + scorecard:
   - `record_closed_trade(row)` → append JSONL to `ROGUE_OPS_HOME/trade_ledger.jsonl` (shared volume, exactly like the shadow ledger).
   - `read_ledger(limit)`.
   - `scorecard(rows)` (pure, testable) → `{trades, win_rate, expectancy_usd, gross_pnl, best, worst, equity_curve, max_drawdown_usd, by_day, cum_pnl}`.
3. **`execution/execution_driver.py`** — in the EXIT branch, right after
   `record_realized_pnl(...)`, call `trade_ledger.record_closed_trade(exit_result)`
   (best-effort, advisory; never breaks execution).
4. **Console** — a "Track Record" panel + `GET /scorecard` (win rate, expectancy,
   equity curve, max drawdown) reading `trade_ledger`. It rides the same
   file-backed bridge the loop already uses.
5. **Go-live gate** — the scorecard's cumulative P&L, win rate, and max drawdown
   over paper-forward become the **quantitative inputs** to the GO/NO-GO in
   `GO_LIVE_PLAN.md` ("paper-forward isn't net-bleeding"). This is the piece that
   turns "it ran" into "here's the measured track record."
6. **Test** — `tools/test_trade_ledger.py`: pairing correctness + scorecard math
   (win rate, expectancy, equity curve, max drawdown) on synthetic closed trades.

**Effort:** ~half a day. **Risk:** low — additive, advisory, persisted like the
shadow ledger, never in the execution decision. **Recommendation: BUILD NOW.** It
directly produces the evidence the go-live gate needs and is exactly the
"measurable track record" worth having before any capital.

### (b) Unified `TradeGateway` (borrow later)
ROGUE's gates are sound but **scattered** (kill switch, daily-loss governor,
capital preflight, `MAX_CAPITAL_CONTRACTS`, unpriceable→fail). IgorGanapolsky's
single pre-broker `TradeGateway` is a cleaner pattern. But several of its checks —
**IV-rank floor, illiquidity rejection, FOMC/event blackout** — need options/IV +
calendar data ROGUE won't have until the **Massive upgrade**. So: fold ROGUE's
existing gates into one `risk/trade_gateway.py` checkpoint **in Week 2**, adding
drawdown-circuit-breaker + position-count + (once data lands) IV-floor/liquidity/
event-blackout. Also adopt their **statistical-correction discipline**: don't
trust an apparent edge (e.g., a day-of-week win-rate) without multiple-testing
correction in the edge verdict.

---

## Sequenced recommendation

1. **Now —** scorecard / paired-trade ledger (§2a). Low-risk, high-value; arms the
   go-live gate with a real track record as paper-forward accrues.
2. **Week 2 (post Massive upgrade) —** unified `TradeGateway` (§2b) with IV/liquidity/
   event gates; multiple-testing correction baked into the edge verdict.
3. **Post-edge / maintenance window —** `ib_async` migration (§1) behind the
   `BrokerRuntime` Protocol + flag, data-feed-first, re-cert. Refactor, not capability.

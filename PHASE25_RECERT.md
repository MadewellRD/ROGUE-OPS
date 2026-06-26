# ROGUE:OPS — Phase 25 Re-Certification Addendum

**Status: CAPITAL authorization INVALIDATED — re-certification required before live capital.**

Per `CAPITAL_GO_LIVE_AUTHORIZATION.md` §7, the prior authorization is automatically
void once execution, risk, envelope, or broker code changes. The multi-broker
rework changed execution-layer code, so a new sign-off is required before any
CAPITAL run. This addendum records what changed and what must be re-verified.

---

## 1. Changes since the prior authorization (execution / risk / broker)

- **Broker boundary introduced.** `broker/broker_runtime.py` — `BrokerRuntime`
  Protocol, `BrokerOrderResult`, and a capability-aware `get_broker_runtime()`
  factory. Execution no longer imports a broker SDK directly.
- **`execution/execution_router.py` (SEALED) edited.** Both broker call sites
  (EXIT, sized ENTRY) now route through the boundary with a fail-closed
  `BROKER_UNSUPPORTED` guard. SIM paths unchanged.
- **Contract limit aligned.** `MAX_CAPITAL_CONTRACTS` 10 → **5**, matching
  authorization §3.2. `MAX_CAPITAL_NOTIONAL_USD` unchanged ($5,000).
- **IBKR is now an implementation, not the spine.** `broker/ibkr_broker.py`
  provides the real order path (`execute_intent`); `broker/ibkr_contracts.py`
  gained an option contract builder; `broker/ibkr_runtime.py` gained monotonic
  order-id sequencing and order-status capture.
- **Robinhood broker added (equities, capability-gated).** `broker/robinhood_*`
  — cannot place options (fail-closed); MCP transport pending live token.
- **Standup/config changes (non-execution but boot-affecting):**
  `governance/paths.py`, `bootstrap_env.py`, `gcp_clients.py`, `main.py`
  (SIM boots without GCP/broker; cross-platform paths).

---

## 2. Re-verification checklist (ALL must be TRUE before CAPITAL)

### Kill switch & envelope (unchanged code — re-confirm)
- [ ] `kill_active()` TRUE blocks envelope creation, router, state machine
- [ ] Envelope seal verified in both `execute()` and `execute_sized()`
- [ ] EXIT bypasses risk but NOT kill

### Broker boundary (new — verify)
- [ ] Options route to IBKR; equities route to configured equity broker
- [ ] Options forced to Robinhood are BLOCKED (`BROKER_UNSUPPORTED`) — fail-closed
- [ ] Unknown `BROKER` value is rejected
- [ ] `tools/test_broker_routing.py` → PASS

### Limits & risk (verify aligned values)
- [ ] `MAX_CAPITAL_CONTRACTS == 5`
- [ ] `MAX_CAPITAL_NOTIONAL_USD == 5000`
- [ ] Notional guard enforced on sized ENTRY
- [ ] Daily loss hard lock active; breach engages kill

### IBKR live order path (verify on paper FIRST)
- [ ] TWS/IB Gateway paper session reachable; API enabled
- [ ] `tools/ibkr_paper_smoke.py` connectivity OK (account summary + order id)
- [ ] `--place` (equity) acknowledges; status observed
- [ ] `--place --opt` (0DTE) acknowledges; **order type reviewed** (currently MKT —
      confirm acceptable or implement marketable-limit before live)
- [ ] Audit record written for the test order

### Determinism / regression
- [ ] `tools/run_sim_regression.py` → PASS (invariants intact)
- [ ] SIM execution path unaffected by router changes

### Environment
- [ ] `EXECUTION_MODE=CAPITAL`, `CAPITAL_ARMED=true` only when intended
- [ ] `OPS_KILL_SWITCH=false` at startup
- [ ] No uncommitted changes in execution-critical files
- [ ] `BROKER` / `EQUITY_BROKER` set to intended backends

---

## 3. Open risks to close before live capital

1. **MKT orders on 0DTE options** — real slippage risk; `ExecutionIntent` has no
   price field. Decide MKT vs marketable-limit. (Tracked: IBKR live-path task.)
2. **IBKR order submission is fire-and-forget** — status capture added, but no
   reconciliation loop. Confirm acknowledgement handling is sufficient for CAPITAL.
3. **Robinhood transport unverified** — equities path gated on live token + probe.

---

## 4. Sign-off

- Re-certified by: __________________________
- Role / Capacity: _________________________
- Date (UTC): ______________________________
- Brokers authorized (IBKR / ROBINHOOD): ____________________
- Signature: _______________________________

**END OF RE-CERTIFICATION ADDENDUM**

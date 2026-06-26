# ROGUE:OPS — SIM Standup Runbook (Windows)

How to stand up and run ROGUE:OPS in **SIM mode** on a Windows dev box.
SIM mode is fully self-contained: **no broker, no Google Cloud, no credentials,
no network calls** on the execution path. It is the safe way to exercise the
full pipeline (market snapshot → signal → state machine → sized execution →
SIM oracle) deterministically.

> Cloud/broker dependencies (`ibapi`, `google-cloud-*`) are required **only**
> for PAPER / LIVE / CAPITAL modes and are intentionally skipped in SIM.

---

## 1. Prerequisites

- Python 3.10+ on PATH (`python --version`)
- This repo checked out at `D:\dev\ROGUE-OPS`

## 2. One-time setup (PowerShell)

```powershell
cd D:\dev\ROGUE-OPS

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install the minimal SIM dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements-sim.txt
```

If activation is blocked by execution policy, run once:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

## 3. Set the SIM environment (PowerShell)

```powershell
$env:OPS_MODE       = "SIM"
$env:OPS_ENV        = "DEV"
$env:OPS_VERSION    = "0.0.0-sim"
$env:EXECUTION_MODE = "SIM"

# Where runtime state (audit logs, data) is written.
# Defaults to %LOCALAPPDATA%\rogueops if unset.
$env:ROGUE_OPS_HOME = "$env:LOCALAPPDATA\rogueops"
```

## 4. Run

```powershell
# A. Boot the application (initializes, then returns in SIM)
python main.py --mode SIM

# B. Run the deterministic SIM trade pipeline end to end
python -m execution.sim_trade_driver

# C. Run the SIM regression harness (compares against the golden record)
python tools\run_sim_regression.py
```

### Expected output

`main.py --mode SIM` ends with:

```
--- Initialization Complete. Starting OPS Authority. ---
[OK] OPS State Machine READY ...
  [OK] Strategy Registry initialized
  [OK] Strategy Feedback Store initialized
```

`python -m execution.sim_trade_driver` ends with:

```
[SIM SIGNAL] INTENT=...
[ASSERTION HASH] 9f5f979fe2f265938112f66c7f4d83575361f08e585005ab52c1f8c09e3fbe68
[SIM ENVELOPE] <hash>
[SIM RESULT] SUBMITTED
[PARITY HASH] <hash>
--- SIM TRADE DRIVER COMPLETE ---
```

`python tools\run_sim_regression.py` ends with:

```
SIM REGRESSION PASS — invariants intact
```

(Envelope and parity hashes are timestamp-derived and intentionally NOT
compared by the regression harness; the indicator-assertion hash and the
execution status ARE compared.)

---

## Notes / gotchas fixed during standup

- **Cross-platform paths.** Runtime paths now resolve from `ROGUE_OPS_HOME`
  (see `governance/paths.py`). The old hardcoded `/opt/rogueops/...` paths
  did not work on Windows.
- **SIM needs no cloud.** `main.py` and `governance/bootstrap_env.py` only
  require GCP/credentials for PAPER/LIVE/CAPITAL. PAPER/LIVE still **fail
  closed** if those are missing.
- **SIM fixture contract.** `execution/sim_trade_driver.py`'s indicator keys
  now match `advisory/signal_engine.py`'s `REQUIRED_INDICATORS`; previously
  they didn't, so the SIM path produced no signal.
- **Regression harness.** `tools/run_sim_regression.py` now invokes the driver
  via `python -m ...` using the current interpreter (was a broken
  `["python3", "sim_trade_driver.py"]`).

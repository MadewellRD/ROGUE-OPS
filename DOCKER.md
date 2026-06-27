# Running ROGUE:OPS always-up

This is the practical guide to keeping the console (and, later, a paper trading
loop) running continuously on this Windows box.

First, the honest mental model: **"always up" is two separate things.**

1. **The console / dashboard.** Stdlib-only, no broker, no risk. Keep it up 24/7.
   That is what `docker compose up -d` below gives you.
2. **The engine actually trading "live."** That only means something on **PAPER**
   (real fills from IB Gateway) — `SIM` is a bootstrap self-test, not a live
   feed. And the strategy is 0DTE: it only acts **10:00–14:30 ET**, is flat by
   **15:55**, and holds nothing overnight, so even "always on" idles most of the
   day. There is **no proven edge yet**, so the ceiling stays paper until the
   shadow/backtest evidence says otherwise.

So: keep the console up now; treat the paper loop as a deliberate later step.

---

## 1. Always-up console (do this now)

Prereqs: Docker Desktop (already installed).

```powershell
cd D:\dev\ROGUE-OPS
# optional: research over Massive + shadow model
"MASSIVE_API_KEY=<your key>"  | Out-File -Encoding ascii .env
"OLLAMA_MODEL=llama3.2"      | Add-Content .env

docker compose up -d --build
```

Open **http://localhost:8787**. That's it — it will stay up and restart itself
on crash (`restart: unless-stopped`).

Useful:

```powershell
docker compose logs -f console     # follow logs
docker compose restart console     # restart
docker compose down                # stop
```

### What persists
State lives in `./.roguedata` (bind-mounted to `/data` as `ROGUE_OPS_HOME`):
the **kill file**, the **shadow ledger**, and audit output. Two consequences:

- An engaged **kill survives restarts** — `restart: unless-stopped` can't
  resurrect a halted trader, because `kill_active()` reads the file on boot.
- The shadow ledger accumulates across restarts, so `shadow_eval` keeps building
  evidence over time.

### Security
- The port is published to **127.0.0.1 only** (`127.0.0.1:8787:8787`) — never the
  LAN. Inside the container the server binds `0.0.0.0` (via `TERMINAL_BIND`); on
  bare metal it still defaults to `127.0.0.1`.
- The Massive key is passed as an env var from `.env`, never baked into the image
  (`.dockerignore` excludes secrets). `.env` and `.roguedata` are gitignored.

### Shadow LLM from the container
The console reaches your host's Ollama at `host.docker.internal:11434`. Make sure
`ollama serve` is running on the host. The Shadow tab's status pill shows UP/DOWN.

---

## 2. Surviving reboots (true "always up")

`restart: unless-stopped` handles crashes, but after a **reboot** the container
only comes back if its supervisor is running. Two ways:

- **Docker Desktop** — enable *Settings → General → Start Docker Desktop when you
  log in*. The container then returns on login. Simple; requires a user session.
- **Native Windows service (most headless)** — your box already runs
  `signaldesk` as a `NT AUTHORITY\SYSTEM` service with no login required. The same
  pattern works here without Docker: run the console under Task Scheduler ("run
  whether user is logged on or not", "at startup", "restart on failure") or wrap
  it with NSSM:

  ```powershell
  nssm install ROGUE-Console python -m api.terminal_server
  nssm set ROGUE-Console AppDirectory D:\dev\ROGUE-OPS
  nssm set ROGUE-Console AppEnvironmentExtra ROGUE_OPS_HOME=D:\dev\ROGUE-OPS\.roguedata
  nssm start ROGUE-Console
  ```

  Native = no Docker Desktop dependency and no login required; Docker = cleaner
  isolation. Either is fine for a personal box.

---

## 3. The engine "live" on paper (later, deliberate)

This is the real "trading all the time" piece. It needs three things the console
doesn't:

1. **IB Gateway, not TWS.** Gateway is the headless, always-up-friendly IBKR
   endpoint. Pair it with **IBC** (IBController) for unattended auto-login and a
   scheduled daily restart. Enable the API, paper port **7497**, and add the
   container's address to **Trusted IPs** (`host-gateway`/`172.17.0.1`-range).
2. **An image with the IBKR Python API (`ibapi`).** The console image omits it on
   purpose. Build a paper image, e.g. `Dockerfile.paper`:

   ```dockerfile
   FROM python:3.12-slim
   WORKDIR /app
   COPY . /app
   ENV PYTHONUNBUFFERED=1 ROGUE_OPS_HOME=/data
   # Install the IBKR API per IB's distribution (it is not reliably on PyPI):
   # COPY vendor/ibapi /tmp/ibapi && pip install /tmp/ibapi
   CMD ["python", "main.py", "--mode", "PAPER"]
   ```

3. **Uncomment the `loop:` service** in `docker-compose.yml` and point it at
   `IBKR_HOST=host.docker.internal`, `IBKR_PORT=7497`. It mounts the same
   `./.roguedata`, so it shares the kill file and writes the shadow ledger.

Because the loop shares `/data`, you can **kill it from the console** (the KILL
button writes `/data/KILL`; the loop halts on its next cycle and won't resume
until you clear the file and restart). That is the control that makes an
auto-restarting trader safe.

Keep it on **PAPER**. Promotion to real capital is gated on a validated edge,
the signed re-cert, and the capital preflight — none of which the container
changes.

---

## Quick reference

| Goal | Command / setting |
|---|---|
| Start console always-up | `docker compose up -d --build` |
| Open dashboard | http://localhost:8787 |
| Follow logs | `docker compose logs -f console` |
| Stop | `docker compose down` |
| Survive reboot | Docker Desktop "start at login" *or* NSSM/Task Scheduler service |
| Engaged kill persists | yes — `./.roguedata/KILL`, honored on boot |
| Research/Massive | set `MASSIVE_API_KEY` in `.env` |
| Shadow LLM | host `ollama serve`; container uses `host.docker.internal:11434` |
| Paper loop | IB Gateway + IBC, `Dockerfile.paper` with `ibapi`, uncomment `loop:` |

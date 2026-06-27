# ROGUE:OPS console image.
#
# The operator console (api/terminal_server) is stdlib-only — no third-party
# deps — so this image stays tiny and builds fast. Research over Massive uses
# urllib (stdlib). The PAPER trading loop additionally needs the IBKR Python API
# (ibapi); that is intentionally NOT installed here — see DOCKER.md for the
# paper-loop image.
#
FROM python:3.12-slim

WORKDIR /app
COPY . /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROGUE_OPS_HOME=/data \
    TERMINAL_BIND=0.0.0.0 \
    TERMINAL_PORT=8787

# Persistent state (kill file, shadow ledger, audit) lives here; mount a volume.
VOLUME ["/data"]
EXPOSE 8787

# Simple liveness check against the JSON state endpoint.
HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('TERMINAL_PORT','8787')+'/state',timeout=3)" || exit 1

CMD ["python", "-m", "api.terminal_server"]

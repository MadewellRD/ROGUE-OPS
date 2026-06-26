#
# tools/massive_probe.py
#
# Discovery probe for the Massive REST API: finds the base URL, auth scheme,
# and response shapes so the data adapter can be built around real payloads.
# Reads MASSIVE_API_KEY from the environment (never hardcoded / committed).
#
#   $env:MASSIVE_API_KEY="..."; python tools\massive_probe.py
#
# Optional: MASSIVE_BASE_URL to pin a base, MASSIVE_SYMBOL (default SPY).
#

import os
import urllib.request
import urllib.parse
import urllib.error

KEY = os.getenv("MASSIVE_API_KEY")
if not KEY:
    raise SystemExit("set MASSIVE_API_KEY")

SYM = os.getenv("MASSIVE_SYMBOL", "SPY")
BASES = (
    [os.getenv("MASSIVE_BASE_URL")]
    if os.getenv("MASSIVE_BASE_URL")
    else ["https://api.massive.com", "https://massive.com", "https://api.massive.io"]
)

PROBES = [
    ("prev_agg",   f"/v2/aggs/ticker/{SYM}/prev"),
    ("snapshot",   f"/v2/snapshot/locale/us/markets/stocks/tickers/{SYM}"),
    ("last_trade", f"/v2/last/trade/{SYM}"),
    ("last_quote", f"/v2/last/nbbo/{SYM}"),
]


def get(url: str, bearer: bool):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    if bearer:
        req.add_header("Authorization", f"Bearer {KEY}")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, r.read(600).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode("utf-8", "replace")
    except Exception as e:
        return None, type(e).__name__ + ": " + str(e)[:90]


print("CODE\tAUTH\tNAME\tURL\tBODY")
for base in BASES:
    for name, ep in PROBES:
        for style in ("bearer", "param"):
            url = base + ep + ("" if style == "bearer" else "?apiKey=" + urllib.parse.quote(KEY))
            code, body = get(url, style == "bearer")
            shown = url if style == "bearer" else base + ep + "?apiKey=***"
            print(f"{code}\t{style}\t{name}\t{shown}\t{body[:180].replace(chr(10),' ').replace(chr(9),' ')}")

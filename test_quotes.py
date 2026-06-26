import os
import requests
import time
import json

STEADYAPI_BASE_URL = "https://api.steadyapi.com"

# Provide the key via environment, never hardcode it:
#   PowerShell:  $env:STEADYAPI_KEY = "your-key"
#   bash:        export STEADYAPI_KEY="your-key"
API_KEY = os.getenv("STEADYAPI_KEY")
if not API_KEY:
    raise SystemExit("STEADYAPI_KEY is not set in the environment")

SYMBOL = "SPY,IWM,QQQ,^VIX"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

while True:
    resp = requests.get(
        f"{STEADYAPI_BASE_URL}/v1/markets/stock/quotes",
        headers=headers,
        params={"ticker": SYMBOL},
        timeout=10,
    )

    print("\n==============================")
    print("HTTP STATUS:", resp.status_code)

    data = resp.json()
    print("RAW RESPONSE:")
    print(json.dumps(data, indent=2))

    body = data.get("body", [])
    if body:
        q = body[0]
        print("\nPARSED FIELDS:")
        print(" marketState        :", q.get("marketState"))
        print(" preMarketPrice    :", q.get("preMarketPrice"))
        print(" regularMarketPrice:", q.get("regularMarketPrice"))
        print(" postMarketPrice   :", q.get("postMarketPrice"))
        print(" preMarketTime     :", q.get("preMarketTime"))
        print(" regularMarketTime :", q.get("regularMarketTime"))
    else:
        print("NO BODY RETURNED")

    time.sleep(3)

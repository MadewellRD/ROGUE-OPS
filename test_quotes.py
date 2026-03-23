import requests
import time
import json

STEADYAPI_BASE_URL = "https://api.steadyapi.com"
API_KEY = "1419|4zMZUQJfKk8Yac6zDkrzTlga3kQCURTy1MNXHBEY"
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

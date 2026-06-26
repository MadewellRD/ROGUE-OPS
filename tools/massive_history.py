#
# tools/massive_history.py
#
# Fetch daily history from Massive (historical data source). Live network call;
# needs a Massive API key (MASSIVE_API_KEY / MASSIVE_API_KEY_FILE / ops_home key file).
#
#   python tools\massive_history.py SPY 30
#   python tools\massive_history.py IWM 60
#

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market.market_data_massive import daily_bars


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    to = dt.datetime.now(dt.timezone.utc).date()
    frm = to - dt.timedelta(days=days * 2 + 5)  # pad for weekends/holidays
    bars = daily_bars(symbol, frm.isoformat(), to.isoformat())[-days:]

    print(f"{symbol} - {len(bars)} daily bars")
    for b in bars:
        vw = f"{b.vwap:.2f}" if b.vwap is not None else "-"
        print(f"  {b.date}  O {b.open:8.2f}  H {b.high:8.2f}  L {b.low:8.2f}  C {b.close:8.2f}  V {b.volume:14,.0f}  VWAP {vw}")


if __name__ == "__main__":
    main()

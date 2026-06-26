#
# tools/test_pricing.py
#
# Unit tests for broker/pricing.py (pure math, no broker required).
#   python tools\test_pricing.py
#

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from broker.pricing import marketable_limit, round_to_tick, UnpriceableError


def main() -> None:
    # BUY pays at the ask; SELL receives at the bid.
    assert marketable_limit("BUY", 1.00, 1.20) == 1.20, "BUY -> ask"
    assert marketable_limit("SELL", 1.00, 1.20) == 1.00, "SELL -> bid"

    # Buffer widens in the aggressive direction only.
    assert marketable_limit("BUY", 1.00, 1.00, buffer_pct=0.05) == 1.05
    assert marketable_limit("SELL", 1.00, 1.00, buffer_pct=0.05) == 0.95

    # Tick rounding.
    assert round_to_tick(1.2345) == 1.23
    assert round_to_tick(1.2367) == 1.24

    # Fail-closed: missing/zero/negative on the needed side raises.
    for side, bid, ask in [("BUY", 1.0, None), ("BUY", 1.0, 0.0),
                           ("BUY", 1.0, -1.0), ("SELL", None, 1.0), ("SELL", 0.0, 1.0)]:
        try:
            marketable_limit(side, bid, ask)
            raise AssertionError(f"expected UnpriceableError for {side} bid={bid} ask={ask}")
        except UnpriceableError:
            pass

    print("PRICING TESTS PASS — marketable limit, buffer, tick rounding, fail-closed")


if __name__ == "__main__":
    main()

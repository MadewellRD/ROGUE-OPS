"""
Vendor Health Audit Log
SMC v1.0 — Read-Only Vendor Validation

This module records the outcome of single-shot vendor
health checks.

ROLE:
- Capture vendor availability signals
- Preserve replay-safe audit records
- Enable operational diagnosis without runtime impact

RULES:
- NO retries
- NO vendor calls
- NO runtime decisions
- Logging only
"""

import datetime as dt
from typing import Optional


def log_vendor_health(
    *,
    vendor: str,
    symbol: str,
    success: bool,
    reason: Optional[str] = None,
) -> None:
    """
    Record vendor health outcome.

    This function is intentionally simple and side-effect free
    beyond logging.
    """

    record = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "vendor": vendor,
        "symbol": symbol,
        "success": success,
        "reason": reason,
    }

    print("[VENDOR][HEALTH]", record)

#
# qualified_contract.py
#
# Qualified Contract (IBKR Canonical Representation)
# PHASE C1 — DATA-ONLY (IMMUTABLE)
#
# Purpose:
# - Represent a fully qualified broker contract
# - Act as a stable, cacheable execution artifact
#
# Explicitly NOT responsible for:
# - Contract discovery
# - Broker communication
# - Execution
# - Risk
#

from dataclasses import dataclass


@dataclass(frozen=True)
class QualifiedContract:
    """
    Immutable representation of a broker-qualified contract.

    This object is:
    - Created only after broker qualification
    - Cached for reuse
    - Passed into execution paths
    """

    symbol: str
    conid: int
    sec_type: str
    exchange: str
    currency: str

    # Option-specific fields (None for non-options)
    expiry: str | None = None
    strike: float | None = None
    right: str | None = None
    multiplier: int | None = None

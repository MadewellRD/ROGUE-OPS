#
# ops_state.py
#
# Global OPS authority
# Sticky, fail-closed, thread-safe
#
# PHASE 18 — SAFETY & RECOVERY AWARE
#

from threading import Lock
from typing import Literal
import os

OPSMode = Literal["CLEAR", "CAUTION", "HALT"]


class _OPSState:
    """
    Global OPS authority.

    CLEAR   → normal operation
    CAUTION → degraded / observability state
    HALT    → sticky, global execution stop

    HALT is intentionally sticky and cannot be cleared
    during normal operation.
    """

    def __init__(self):
        self._state: OPSMode = "CLEAR"
        self._lock = Lock()

    # ----------------------------
    # Read access
    # ----------------------------

    def get(self) -> OPSMode:
        return self._state

    def is_halted(self) -> bool:
        return self._state == "HALT"

    # ----------------------------
    # Transitions
    # ----------------------------

    def halt(self, reason: str = ""):
        """
        Enter HALT state.
        Sticky by design.
        """
        with self._lock:
            self._state = "HALT"

    def caution(self):
        """
        Enter CAUTION state.
        No execution effect yet.
        """
        with self._lock:
            if self._state != "HALT":
                self._state = "CAUTION"

    def clear(self):
        """
        Clear CAUTION → CLEAR.
        HALT cannot be cleared programmatically.
        """
        with self._lock:
            if self._state == "CAUTION":
                self._state = "CLEAR"

    # ----------------------------
    # TEST / VALIDATION ONLY
    # ----------------------------

    def _force_clear_for_test(self):
        """
        FORCE CLEAR OPS STATE.

        TEST / VALIDATION ONLY.
        Requires OPS_ALLOW_TEST_RESET=true.

        This method MUST NOT be used in production.
        """
        if os.getenv("OPS_ALLOW_TEST_RESET") != "true":
            raise RuntimeError("OPS HALT reset not permitted")

        with self._lock:
            self._state = "CLEAR"


# ----------------------------
# Singleton accessor
# ----------------------------

_OPS = _OPSState()


def get_ops_state() -> _OPSState:
    return _OPS

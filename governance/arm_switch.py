#
# governance/arm_switch.py
#
# Operator ARM gate (cross-process, durable) — ROGUE-009.
#
# Mirrors the kill-switch pattern: a file under ROGUE_OPS_HOME ("ARM") whose
# presence means the operator has explicitly armed live autonomy. The console
# writes it via api/control.set_arm; this module is the canonical reader so the
# execution authority can enforce it WITHOUT importing the api layer.
#
# Semantics (deliberately the inverse of kill):
#   - KILL is dominant + restrictive: present => stop. Fail-closed.
#   - ARM is permissive + necessary-not-sufficient: absent => PAPER/CAPITAL
#     entries are denied; present => entries may proceed (CAPITAL still passes
#     the capital gate downstream). SIM is exempt and never consults ARM.
#
# This makes the console ARM button a real control instead of cosmetic.
#

from governance.paths import ops_home


def arm_active() -> bool:
    """True iff the durable ARM file exists under ROGUE_OPS_HOME. Fail-safe:
    any error reading it is treated as DISARMED (deny), never armed."""
    try:
        return (ops_home() / "ARM").exists()
    except Exception:
        return False

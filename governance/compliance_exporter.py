#
# compliance_exporter.py
#
# Compliance & Regulatory Export Authority
# PHASE 27 — REGULATORY-GRADE EXPORT (ATOMIC)
#
# Responsible for:
# - Exporting immutable audit trails
# - Producing regulator-grade artifacts
# - Preserving hash-chain integrity
#
# Explicitly NOT responsible for:
# - Execution
# - Risk
# - State mutation
# - Record construction
#

import json
import csv
from typing import List, Dict, Any
from pathlib import Path

from audit_store import get_audit_store


class ComplianceExporter:
    """
    Deterministic compliance export authority.

    Reads from the authoritative AuditStore and
    emits immutable, replay-safe artifacts.
    """

    def __init__(self):
        self.audit = get_audit_store()

    # ==================================================
    # Core retrieval
    # ==================================================

    def _records(self) -> List[Dict[str, Any]]:
        records = self.audit.all_records()
        if not records:
            raise RuntimeError("No audit records available for export")
        return records

    # ==================================================
    # JSON EXPORT (ARCHIVAL / MACHINE)
    # ==================================================

    def export_json(self, path: str) -> None:
        """
        Export full audit trail as deterministic JSON.
        """
        records = self._records()

        payload = {
            "format": "ROGUE_OPS_COMPLIANCE_JSON",
            "record_count": len(records),
            "records": records,
        }

        Path(path).write_text(
            json.dumps(payload, indent=2, sort_keys=True)
        )

    # ==================================================
    # CSV EXPORT (ACCOUNTING / REGULATORY)
    # ==================================================

    def export_csv(self, path: str) -> None:
        """
        Export flattened audit trail as CSV.
        """
        records = self._records()

        fieldnames = [
            "seq",
            "record_type",
            "created_at_utc",
            "record_hash",
            "prev_hash",
            "envelope_hash",
            "kill_active",
            "kill_reason",
            "kill_timestamp_utc",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for r in records:
                kc = r.get("kill_context", {})
                writer.writerow(
                    {
                        "seq": r.get("seq"),
                        "record_type": r.get("record_type"),
                        "created_at_utc": r.get("created_at_utc"),
                        "record_hash": r.get("record_hash"),
                        "prev_hash": r.get("prev_hash"),
                        "envelope_hash": r.get("envelope_hash"),
                        "kill_active": kc.get("killed"),
                        "kill_reason": kc.get("reason"),
                        "kill_timestamp_utc": kc.get("timestamp_utc"),
                    }
                )

    # ==================================================
    # HUMAN READABLE REPORT (INVESTOR / COUNSEL)
    # ==================================================

    def export_report(self, path: str) -> None:
        """
        Export human-readable compliance report.
        """
        records = self._records()

        lines = []
        lines.append("ROGUE:OPS COMPLIANCE REPORT")
        lines.append("=" * 40)
        lines.append(f"Total Records: {len(records)}")
        lines.append("")

        for r in records:
            lines.append(f"SEQ {r['seq']} | {r['record_type']}")
            lines.append(f"  Time (UTC): {r['created_at_utc']}")
            lines.append(f"  Record Hash: {r['record_hash']}")
            lines.append(f"  Prev Hash  : {r['prev_hash']}")
            lines.append(f"  Envelope  : {r['envelope_hash']}")

            kc = r.get("kill_context", {})
            if kc.get("killed"):
                lines.append("  KILL STATE:")
                lines.append(f"    Reason: {kc.get('reason')}")
                lines.append(f"    Time  : {kc.get('timestamp_utc')}")

            lines.append("")

        Path(path).write_text("\n".join(lines))


# ==================================================
# Convenience CLI (OPTIONAL, NON-AUTHORITATIVE)
# ==================================================

if __name__ == "__main__":
    exporter = ComplianceExporter()
    exporter.export_json("compliance_audit.json")
    exporter.export_csv("compliance_audit.csv")
    exporter.export_report("compliance_report.txt")

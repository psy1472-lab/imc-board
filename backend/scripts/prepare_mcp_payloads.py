"""Prepare JSON payloads for Supabase MCP execute_sql migration."""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = PROJECT_ROOT / "data" / "postgres_batches"
PAYLOAD_DIR = BATCH_DIR / "_mcp_payloads"

TABLE_ORDER = [
    "report_metadata",
    "daily_summary",
    "hourly_throughput",
    "staffing",
    "quota_exchange",
    "transport_office",
    "sorting_machine",
    "safety_summary",
    "safety_incident",
    "anomaly",
    "validation_log",
    "kpi_comparison",
    "threshold_config",
    "operation_period",
]


def main() -> None:
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    idx = 0
    manifest: list[dict] = []
    for table in TABLE_ORDER:
        for path in sorted(BATCH_DIR.glob(f"{table}_*.sql")):
            sql = path.read_text(encoding="utf-8")
            payload = {"index": idx, "file": path.name, "table": table, "sql": sql}
            out = PAYLOAD_DIR / f"{idx:04d}_{path.name}.json"
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            manifest.append({"index": idx, "file": path.name, "table": table, "payload": out.name, "bytes": len(sql)})
            idx += 1
    (PAYLOAD_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(manifest)} payloads in {PAYLOAD_DIR}")


if __name__ == "__main__":
    main()

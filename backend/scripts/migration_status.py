"""Apply all postgres batch files; prints progress for MCP-driven migration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = PROJECT_ROOT / "data" / "postgres_batches"
PAYLOAD_DIR = BATCH_DIR / "_mcp_payloads"
STATUS_FILE = PAYLOAD_DIR / "migration_status.json"

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


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "errors": []}


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def list_pending() -> list[dict]:
    status = load_status()
    done = set(status.get("completed", []))
    pending: list[dict] = []
    idx = 0
    for table in TABLE_ORDER:
        for path in sorted(BATCH_DIR.glob(f"{table}_*.sql")):
            if path.name in done:
                idx += 1
                continue
            pending.append({"index": idx, "file": path.name, "table": table, "path": str(path)})
            idx += 1
    return pending


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if cmd == "pending":
        pending = list_pending()
        print(json.dumps(pending[:20], ensure_ascii=False))
        print(f"TOTAL_PENDING={len(pending)}", file=sys.stderr)
        return
    if cmd == "mark":
        name = sys.argv[2]
        status = load_status()
        if name not in status["completed"]:
            status["completed"].append(name)
        save_status(status)
        print(f"MARKED {name}")
        return
    if cmd == "error":
        name = sys.argv[2]
        msg = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        status = load_status()
        status.setdefault("errors", []).append({"file": name, "error": msg})
        save_status(status)
        print(f"ERROR {name}: {msg}")
        return
    if cmd == "sql":
        name = sys.argv[2]
        path = BATCH_DIR / name
        sys.stdout.write(path.read_text(encoding="utf-8"))
        return
    if cmd == "init":
        save_status({"completed": ["threshold_config_0000.sql", "operation_period_0000.sql"], "errors": []})
        print("INIT")
        return
    raise SystemExit(f"unknown cmd: {cmd}")


if __name__ == "__main__":
    main()

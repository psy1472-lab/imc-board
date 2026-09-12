"""Apply pending MCP migration payloads to Postgres via DATABASE_URL.

Mirrors the MCP execute_sql migration workflow: reads JSON payloads in index
order, skips completed files, splits oversized SQL at row boundaries on failure,
updates migration_status.json, and verifies row counts per table.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"
STATUS_FILE = PAYLOAD_DIR / "migration_status.json"
MANIFEST_FILE = PAYLOAD_DIR / "manifest.json"

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

EXPECTED_COUNTS = {
    "report_metadata": 480,
    "daily_summary": 480,
    "hourly_throughput": 6720,
    "staffing": 6720,
    "quota_exchange": 473,
    "transport_office": 6329,
    "sorting_machine": 475,
    "safety_summary": 3284,
    "safety_incident": 205,
    "anomaly": 1816,
    "validation_log": 1435,
    "kpi_comparison": 2928,
    "threshold_config": 1,
    "operation_period": 10,
}

SIZE_ERROR_MARKERS = (
    "payload too large",
    "query too long",
    "statement too long",
    "request entity too large",
    "max_allowed_packet",
    "too many",
)


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "errors": []}


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_completed(filename: str) -> None:
    status = load_status()
    if filename not in status["completed"]:
        status["completed"].append(filename)
    save_status(status)


def record_error(filename: str, msg: str) -> None:
    status = load_status()
    status.setdefault("errors", []).append({"file": filename, "error": msg})
    save_status(status)


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def pending_entries() -> list[dict]:
    done = set(load_status().get("completed", []))
    return [e for e in load_manifest() if e["file"] not in done]


def split_sql_at_rows(sql: str) -> tuple[str, str]:
    """Split INSERT ... VALUES (...), (...); at roughly half the row tuples."""
    values_match = re.search(r"\bVALUES\b", sql, flags=re.IGNORECASE)
    if not values_match:
        raise ValueError("cannot split: no VALUES clause")

    prefix = sql[: values_match.end()]
    rest = sql[values_match.end() :].lstrip()

    on_conflict_match = re.search(r"\n\s*ON CONFLICT\b", rest, flags=re.IGNORECASE)
    if on_conflict_match:
        values_part = rest[: on_conflict_match.start()].rstrip()
        suffix = rest[on_conflict_match.start() :]
    else:
        values_part = rest.rstrip().removesuffix(";")
        suffix = ";"

    rows: list[str] = []
    depth = 0
    start = 0
    for idx, ch in enumerate(values_part):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                segment = values_part[start : idx + 1].strip()
                if segment.startswith(","):
                    segment = segment[1:].strip()
                if segment:
                    rows.append(segment)
                start = idx + 1

    if len(rows) < 2:
        raise ValueError("cannot split: fewer than 2 rows")

    mid = len(rows) // 2
    first = prefix + " " + ", ".join(rows[:mid]) + suffix
    second = prefix + " " + ", ".join(rows[mid:]) + suffix
    return first, second


def is_size_error(msg: str) -> bool:
    lower = msg.lower()
    return any(marker in lower for marker in SIZE_ERROR_MARKERS)


def connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("pip install psycopg[binary] required") from exc
    return psycopg.connect(database_url)


def execute_sql(conn, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)


def execute_with_split(conn, sql: str, filename: str) -> None:
    try:
        execute_sql(conn, sql)
    except Exception as exc:
        if not is_size_error(str(exc)):
            raise
        first, second = split_sql_at_rows(sql)
        print(f"SPLIT {filename}", file=sys.stderr)
        execute_sql(conn, first)
        execute_sql(conn, second)


def table_batches(manifest: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {t: [] for t in TABLE_ORDER}
    for entry in manifest:
        grouped.setdefault(entry["table"], []).append(entry["file"])
    return grouped


def verify_table_count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith("postgres"):
        print("FAIL: set DATABASE_URL=postgresql://...", file=sys.stderr)
        return 1

    pending = pending_entries()
    if not pending:
        print("No pending batches.")
    else:
        print(f"Processing {len(pending)} pending batches...", file=sys.stderr)

    manifest = load_manifest()
    batches_by_table = table_batches(manifest)
    completed_before = set(load_status().get("completed", []))
    newly_completed: list[str] = []
    errors: list[dict] = []

    conn = connect(database_url)
    try:
        current_table: str | None = None
        for entry in pending:
            table = entry["table"]
            filename = entry["file"]
            payload_path = PAYLOAD_DIR / entry["payload"]
            data = json.loads(payload_path.read_text(encoding="utf-8"))
            sql = data["sql"]

            if current_table and table != current_table:
                count = verify_table_count(conn, current_table)
                expected = EXPECTED_COUNTS.get(current_table)
                ok = "OK" if count == expected else "MISMATCH"
                print(f"VERIFY {current_table}: {count} (expected {expected}) [{ok}]")

            current_table = table
            try:
                execute_with_split(conn, sql, filename)
                conn.commit()
                mark_completed(filename)
                newly_completed.append(filename)
                print(f"OK {filename}")
            except Exception as exc:
                conn.rollback()
                msg = str(exc)
                record_error(filename, msg)
                errors.append({"file": filename, "error": msg})
                print(f"ERROR {filename}: {msg}", file=sys.stderr)
                return 1

        if current_table:
            count = verify_table_count(conn, current_table)
            expected = EXPECTED_COUNTS.get(current_table)
            ok = "OK" if count == expected else "MISMATCH"
            print(f"VERIFY {current_table}: {count} (expected {expected}) [{ok}]")
    finally:
        conn.close()

    verify = connect(database_url)
    try:
        print("\n=== FINAL COUNTS ===")
        summary: dict[str, dict] = {}
        for table in TABLE_ORDER:
            count = verify_table_count(verify, table)
            expected = EXPECTED_COUNTS[table]
            summary[table] = {
                "count": count,
                "expected": expected,
                "match": count == expected,
            }
            flag = "OK" if count == expected else "MISMATCH"
            print(f"  {table}: {count} / {expected} [{flag}]")
    finally:
        verify.close()

    status = load_status()
    total_completed = len(status.get("completed", []))
    print(f"\nCompleted batches: {total_completed}/136")
    print(f"Newly completed this run: {len(newly_completed)}")
    print(f"Errors: {len(status.get('errors', []))}")
    for err in status.get("errors", []):
        print(f"  - {err['file']}: {err['error'][:200]}")

    all_match = all(v["match"] for v in summary.values())
    return 0 if all_match and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

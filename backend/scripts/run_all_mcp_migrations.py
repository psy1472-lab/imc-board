"""Run all MCP migration payloads via Supabase execute_sql HTTP bridge.

Uses SUPABASE_ACCESS_TOKEN + project ref from env, or falls back to printing
instructions. Primary path for agent: call execute_sql MCP per batch.

This script applies all pending batches when DATABASE_URL is set (direct psycopg).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Reuse apply_mcp_payloads logic
sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_mcp_payloads import (  # noqa: E402
    EXPECTED_COUNTS,
    TABLE_ORDER,
    connect,
    execute_with_split,
    load_manifest,
    load_status,
    mark_completed,
    pending_entries,
    record_error,
    save_status,
    verify_table_count,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"


def apply_all(database_url: str) -> int:
    pending = pending_entries()
    if not pending:
        print("No pending batches.")
    else:
        print(f"Processing {len(pending)} pending batches...", file=sys.stderr)

    conn = connect(database_url)
    errors: list[dict] = []
    try:
        for entry in pending:
            filename = entry["file"]
            payload_path = PAYLOAD_DIR / entry["payload"]
            sql = json.loads(payload_path.read_text(encoding="utf-8"))["sql"]
            try:
                execute_with_split(conn, sql, filename)
                conn.commit()
                mark_completed(filename)
                print(f"OK {filename}")
            except Exception as exc:
                conn.rollback()
                msg = str(exc)
                record_error(filename, msg)
                errors.append({"file": filename, "error": msg})
                print(f"ERROR {filename}: {msg}", file=sys.stderr)
                return 1
    finally:
        conn.close()

    verify = connect(database_url)
    try:
        print("\n=== FINAL COUNTS ===")
        summary = {}
        for table in TABLE_ORDER:
            count = verify_table_count(verify, table)
            expected = EXPECTED_COUNTS.get(table, count)
            summary[table] = {"count": count, "expected": expected, "match": count == expected}
            flag = "OK" if count == expected else "MISMATCH"
            print(f"  {table}: {count} / {expected} [{flag}]")
    finally:
        verify.close()

    status = load_status()
    print(f"\nCompleted: {len(status.get('completed', []))}/136")
    print(f"Errors: {len(status.get('errors', []))}")
    return 0 if not errors else 1


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("postgres"):
        return apply_all(database_url)
    print("DATABASE_URL not set; use MCP execute_sql per batch.", file=sys.stderr)
    pending = pending_entries()
    print(json.dumps([{"index": e["index"], "file": e["file"]} for e in pending[:5]]))
    print(f"TOTAL_PENDING={len(pending)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

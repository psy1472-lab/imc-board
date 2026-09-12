"""Apply MCP migration payloads using migrate_sqlite_to_postgres logic via psycopg.

Reads pending batches from manifest and applies SQL from payload files.
Use when DATABASE_URL is valid.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Reuse helpers from apply_mcp_payloads
sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_mcp_payloads import (  # noqa: E402
    connect,
    execute_with_split,
    load_manifest,
    load_status,
    pending_entries,
    save_status,
    verify_table_count,
    TABLE_ORDER,
    EXPECTED_COUNTS,
)

PAYLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "postgres_batches" / "_mcp_payloads"


def load_sql(entry: dict) -> str:
    payload = PAYLOAD_DIR / entry["payload"]
    return json.loads(payload.read_text(encoding="utf-8"))["sql"]


def mark_completed(filename: str) -> None:
    status = load_status()
    if filename not in status["completed"]:
        status["completed"].append(filename)
    save_status(status)


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url.startswith("postgres"):
        print("FAIL: set DATABASE_URL=postgresql://...", file=sys.stderr)
        return 1

    pending = pending_entries()
    if not pending:
        print("No pending batches.")
        return 0

    print(f"Applying {len(pending)} batches...", file=sys.stderr)
    conn = connect(database_url)
    try:
        for i, entry in enumerate(pending, 1):
            sql = load_sql(entry)
            filename = entry["file"]
            execute_with_split(conn, sql, filename)
            conn.commit()
            mark_completed(filename)
            print(f"[{i}/{len(pending)}] OK {filename}")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR {entry['file']}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    verify = connect(database_url)
    try:
        print("\n=== FINAL COUNTS ===")
        all_ok = True
        for table in TABLE_ORDER:
            count = verify_table_count(verify, table)
            expected = EXPECTED_COUNTS[table]
            ok = count == expected
            all_ok = all_ok and ok
            flag = "OK" if ok else "MISMATCH"
            print(f"  {table}: {count} / {expected} [{flag}]")
    finally:
        verify.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

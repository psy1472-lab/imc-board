"""Apply all pending MCP migration batches by reading payload SQL files.

When --via-mcp is set, writes each batch SQL to _current_batch.json and waits
for external MCP execute_sql + mark-ok. For direct apply, set DATABASE_URL.

Usage:
  python mcp_apply_all.py --direct          # requires DATABASE_URL
  python mcp_apply_all.py --prepare 0       # write batch 0 SQL for MCP
  python mcp_apply_all.py --loop-direct     # apply all via psycopg
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from apply_mcp_payloads import (  # noqa: E402
    connect,
    execute_with_split,
    load_status,
    mark_completed,
    pending_entries,
    record_error,
    save_status,
    verify_table_count,
    EXPECTED_COUNTS,
    TABLE_ORDER,
    PAYLOAD_DIR,
)

CURRENT_BATCH = PAYLOAD_DIR / "_current_batch.json"


def load_sql(entry: dict) -> str:
    payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
    return payload["sql"]


def prepare_batch(index: int) -> dict:
    from mcp_apply_one import get_entry

    entry = get_entry(index)
    return {
        "index": index,
        "file": entry["file"],
        "table": entry["table"],
        "sql": load_sql(entry),
    }


def apply_all_direct(database_url: str) -> int:
    pending = pending_entries()
    if not pending:
        print("No pending batches.")
        return 0

    conn = connect(database_url)
    errors = 0
    try:
        for entry in pending:
            fn = entry["file"]
            sql = load_sql(entry)
            try:
                execute_with_split(conn, sql, fn)
                conn.commit()
                mark_completed(fn)
                print(f"OK {fn}")
            except Exception as exc:
                conn.rollback()
                record_error(fn, str(exc))
                print(f"ERROR {fn}: {exc}", file=sys.stderr)
                errors += 1
                return 1
    finally:
        conn.close()

    conn = connect(database_url)
    try:
        print("\n=== FINAL COUNTS ===")
        for table in TABLE_ORDER:
            cnt = verify_table_count(conn, table)
            exp = EXPECTED_COUNTS.get(table, "?")
            flag = "OK" if cnt == exp else "MISMATCH"
            print(f"  {table}: {cnt} / {exp} [{flag}]")
    finally:
        conn.close()

    s = load_status()
    print(f"\nCompleted: {len(s['completed'])}/136, Errors: {len(s.get('errors', []))}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--prepare", type=int)
    ap.add_argument("--pending-count", action="store_true")
    args = ap.parse_args()

    if args.pending_count:
        print(len(pending_entries()))
        return 0

    if args.prepare is not None:
        data = prepare_batch(args.prepare)
        CURRENT_BATCH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"index": data["index"], "file": data["file"], "table": data["table"], "bytes": len(data["sql"])}))
        return 0

    if args.direct:
        db = os.getenv("DATABASE_URL", "").strip()
        if not db.startswith("postgres"):
            print("FAIL: DATABASE_URL required", file=sys.stderr)
            return 1
        return apply_all_direct(db)

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

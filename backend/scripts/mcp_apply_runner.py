"""Apply all pending migration batches using Supabase MCP execute_sql via Cursor agent loop.

This script prepares batch jobs and marks completion. The agent reads each job's
sql_file and calls user-supabase execute_sql, then runs:
  python mcp_apply_runner.py --complete <index>

Or for fully automated direct apply (requires DATABASE_URL):
  python mcp_apply_runner.py --apply-all-direct
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
    pending_entries,
    mark_completed,
    record_error,
    verify_table_count,
    EXPECTED_COUNTS,
    TABLE_ORDER,
    PAYLOAD_DIR,
)
from mcp_agent_loop import ensure_sql_file  # noqa: E402

JOBS_DIR = PAYLOAD_DIR / "_jobs"


def prepare_jobs() -> int:
    JOBS_DIR.mkdir(exist_ok=True)
    count = 0
    for entry in pending_entries():
        sql_path = ensure_sql_file(entry)
        job = {
            "index": entry["index"],
            "file": entry["file"],
            "table": entry["table"],
            "sql_file": str(sql_path),
        }
        job_path = JOBS_DIR / f"{entry['index']:04d}.json"
        job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        count += 1
    print(json.dumps({"prepared": count, "jobs_dir": str(JOBS_DIR)}))
    return 0


def next_job() -> int:
    for entry in pending_entries():
        job_path = JOBS_DIR / f"{entry['index']:04d}.json"
        if not job_path.exists():
            ensure_sql_file(entry)
            job = {
                "index": entry["index"],
                "file": entry["file"],
                "table": entry["table"],
                "sql_file": str(PAYLOAD_DIR / "_sql_cache" / f"{entry['index']:04d}.sql"),
            }
            job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        job = json.loads(job_path.read_text(encoding="utf-8"))
        sql = Path(job["sql_file"]).read_text(encoding="utf-8")
        print(json.dumps({**job, "sql": sql}, ensure_ascii=False))
        return 0
    print("NONE")
    return 0


def complete(index: int) -> int:
    from mcp_apply_one import get_entry
    entry = get_entry(index)
    mark_completed(entry["file"])
    job_path = JOBS_DIR / f"{index:04d}.json"
    if job_path.exists():
        job_path.unlink()
    remaining = len(pending_entries())
    print(json.dumps({"ok": True, "file": entry["file"], "remaining": remaining}))
    return 0


def fail(index: int, msg: str) -> int:
    from mcp_apply_one import get_entry
    entry = get_entry(index)
    record_error(entry["file"], msg)
    print(json.dumps({"ok": False, "file": entry["file"], "error": msg}))
    return 0


def apply_all_direct() -> int:
    db = os.getenv("DATABASE_URL", "").strip()
    if not db.startswith("postgres"):
        print("FAIL: DATABASE_URL required", file=sys.stderr)
        return 1
    pending = pending_entries()
    conn = connect(db)
    try:
        for entry in pending:
            sql_path = ensure_sql_file(entry)
            sql = sql_path.read_text(encoding="utf-8")
            fn = entry["file"]
            try:
                execute_with_split(conn, sql, fn)
                conn.commit()
                mark_completed(fn)
                print(f"OK {fn}")
            except Exception as exc:
                conn.rollback()
                record_error(fn, str(exc))
                print(f"ERROR {fn}: {exc}", file=sys.stderr)
                return 1
    finally:
        conn.close()
    conn = connect(db)
    try:
        for table in TABLE_ORDER:
            cnt = verify_table_count(conn, table)
            exp = EXPECTED_COUNTS.get(table, "?")
            print(f"{table}: {cnt}/{exp}")
    finally:
        conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--complete", type=int)
    ap.add_argument("--fail", nargs=2, metavar=("INDEX", "MSG"))
    ap.add_argument("--apply-all-direct", action="store_true")
    ap.add_argument("--pending-count", action="store_true")
    args = ap.parse_args()

    if args.pending_count:
        print(len(pending_entries()))
        return 0
    if args.prepare:
        return prepare_jobs()
    if args.next:
        return next_job()
    if args.complete is not None:
        return complete(args.complete)
    if args.fail:
        return fail(int(args.fail[0]), args.fail[1])
    if args.apply_all_direct:
        return apply_all_direct()
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

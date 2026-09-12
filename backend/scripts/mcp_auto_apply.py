"""Apply all pending migration batches via Supabase MCP execute_sql.

Reads cached SQL files and writes a job queue. Agent/MCP runner processes each job.
For fully automated apply when DATABASE_URL is available, use apply_mcp_payloads.py.

Usage:
  python mcp_auto_apply.py --queue          # list pending jobs as JSON lines
  python mcp_auto_apply.py --apply-one 5    # print SQL for batch index 5
  python mcp_auto_apply.py --mark 5         # mark batch 5 completed by index
  python mcp_auto_apply.py --mark-file FILE # mark by filename
  python mcp_auto_apply.py --split 99       # print split SQL parts for batch 99
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from apply_mcp_payloads import (  # noqa: E402
    PAYLOAD_DIR,
    load_status,
    mark_completed,
    pending_entries,
    record_error,
    split_sql_at_rows,
)
from mcp_agent_loop import ensure_sql_file  # noqa: E402


def get_by_index(index: int) -> dict:
    from mcp_apply_one import get_entry
    entry = get_entry(index)
    sql_path = ensure_sql_file(entry)
    return {
        "index": entry["index"],
        "file": entry["file"],
        "table": entry["table"],
        "sql": sql_path.read_text(encoding="utf-8"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--apply-one", type=int)
    ap.add_argument("--mark", type=int)
    ap.add_argument("--mark-file", type=str)
    ap.add_argument("--mark-err", nargs=2, metavar=("FILE", "MSG"))
    ap.add_argument("--split", type=int)
    ap.add_argument("--pending-count", action="store_true")
    args = ap.parse_args()

    if args.pending_count:
        print(len(pending_entries()))
        return 0

    if args.queue:
        for entry in pending_entries():
            sql_path = ensure_sql_file(entry)
            print(json.dumps({
                "index": entry["index"],
                "file": entry["file"],
                "table": entry["table"],
                "bytes": sql_path.stat().st_size,
            }))
        return 0

    if args.apply_one is not None:
        job = get_by_index(args.apply_one)
        print(json.dumps({"index": job["index"], "file": job["file"], "table": job["table"], "sql": job["sql"]}, ensure_ascii=False))
        return 0

    if args.split is not None:
        job = get_by_index(args.split)
        first, second = split_sql_at_rows(job["sql"])
        print(json.dumps({"index": job["index"], "file": job["file"], "part1": first, "part2": second}, ensure_ascii=False))
        return 0

    if args.mark is not None:
        from mcp_apply_one import get_entry
        entry = get_entry(args.mark)
        mark_completed(entry["file"])
        print(json.dumps({"ok": True, "file": entry["file"]}))
        return 0

    if args.mark_file:
        mark_completed(args.mark_file)
        print(json.dumps({"ok": True, "file": args.mark_file}))
        return 0

    if args.mark_err:
        record_error(args.mark_err[0], args.mark_err[1])
        print(json.dumps({"ok": False, "file": args.mark_err[0]}))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

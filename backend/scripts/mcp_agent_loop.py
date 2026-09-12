"""Process pending MCP batches: load SQL from payloads, apply via callback.

Agent usage - run with --emit-range to get batch metadata, then for each:
  python mcp_agent_loop.py --emit-range 1 5
  -> prints JSON array [{index, file, sql_path}]

Direct MCP loop (agent reads sql_path, calls execute_sql, then):
  python mcp_agent_loop.py --mark-range-ok 1 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from apply_mcp_payloads import PAYLOAD_DIR, load_status, mark_completed, pending_entries  # noqa: E402

SQL_CACHE = PAYLOAD_DIR / "_sql_cache"


def ensure_sql_file(entry: dict) -> Path:
    SQL_CACHE.mkdir(exist_ok=True)
    out = SQL_CACHE / f"{entry['index']:04d}.sql"
    if not out.exists():
        payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
        out.write_text(payload["sql"], encoding="utf-8")
    return out


def emit_range(start: int, count: int) -> list[dict]:
    pending = pending_entries()
    out = []
    for entry in pending:
        if entry["index"] < start:
            continue
        if len(out) >= count:
            break
        sql_path = ensure_sql_file(entry)
        out.append({
            "index": entry["index"],
            "file": entry["file"],
            "table": entry["table"],
            "sql_path": str(sql_path),
            "bytes": sql_path.stat().st_size,
        })
    return out


def mark_range_ok(start: int, count: int) -> int:
    pending = pending_entries()
    marked = 0
    for entry in pending:
        if entry["index"] < start:
            continue
        if marked >= count:
            break
        mark_completed(entry["file"])
        marked += 1
    return marked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-range", nargs=2, type=int, metavar=("START", "COUNT"))
    ap.add_argument("--mark-range-ok", nargs=2, type=int, metavar=("START", "COUNT"))
    ap.add_argument("--pending", action="store_true")
    ap.add_argument("--read-sql", type=int)
    args = ap.parse_args()

    if args.pending:
        pending = pending_entries()
        print(json.dumps([e["index"] for e in pending]))
        return 0

    if args.read_sql is not None:
        from mcp_apply_one import get_entry
        entry = get_entry(args.read_sql)
        sql_path = ensure_sql_file(entry)
        sys.stdout.write(sql_path.read_text(encoding="utf-8"))
        return 0

    if args.emit_range:
        start, count = args.emit_range
        print(json.dumps(emit_range(start, count), ensure_ascii=False))
        return 0

    if args.mark_range_ok:
        start, count = args.mark_range_ok
        n = mark_range_ok(start, count)
        print(json.dumps({"marked": n}))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

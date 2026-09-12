"""Apply all pending MCP migration batches via Supabase execute_sql MCP tool.

Reads payload SQL files, executes each via MCP (agent-driven) or direct psycopg
when DATABASE_URL is set. Updates migration_status.json after each batch.

Agent usage:
  python apply_mcp_via_runner.py --start 0 --count 8 --emit-only
  -> prints JSON array of {index, file, sql} for MCP execute_sql calls

Direct usage:
  DATABASE_URL=postgresql://... python apply_mcp_via_runner.py --apply-all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"
STATUS_FILE = PAYLOAD_DIR / "migration_status.json"
MANIFEST_FILE = PAYLOAD_DIR / "manifest.json"

EXPECTED = {
    "report_metadata": 480,
    "daily_summary": 480,
    "hourly_throughput": 6720,
    "staffing": 6720,
    "quota_exchange": 411,
    "transport_office": 6329,
    "sorting_machine": 475,
    "safety_summary": 3281,
    "safety_incident": 205,
    "anomaly": 1816,
    "validation_log": 1435,
    "kpi_comparison": 2915,
    "threshold_config": 1,
    "operation_period": 10,
}


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "errors": []}


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_completed(filename: str) -> None:
    s = load_status()
    if filename not in s["completed"]:
        s["completed"].append(filename)
    save_status(s)


def record_error(filename: str, msg: str) -> None:
    s = load_status()
    s.setdefault("errors", []).append({"file": filename, "error": msg})
    save_status(s)


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def pending() -> list[dict]:
    done = set(load_status().get("completed", []))
    return [e for e in load_manifest() if e["file"] not in done]


def load_sql(entry: dict) -> str:
    p = PAYLOAD_DIR / entry["payload"]
    return json.loads(p.read_text(encoding="utf-8"))["sql"]


def emit_batch(entry: dict) -> dict:
    return {
        "index": entry["index"],
        "file": entry["file"],
        "table": entry["table"],
        "sql": load_sql(entry),
    }


def apply_all_direct(database_url: str) -> int:
    from apply_mcp_payloads import connect, execute_with_split, verify_table_count

    entries = pending()
    conn = connect(database_url)
    try:
        for entry in entries:
            fn = entry["file"]
            sql = load_sql(entry)
            try:
                execute_with_split(conn, sql, fn)
                conn.commit()
                mark_completed(fn)
                print(f"OK {fn}", file=sys.stderr)
            except Exception as exc:
                conn.rollback()
                record_error(fn, str(exc))
                print(f"ERROR {fn}: {exc}", file=sys.stderr)
                return 1
    finally:
        conn.close()

    conn = connect(database_url)
    try:
        print("=== VERIFY ===")
        for table, exp in EXPECTED.items():
            cnt = verify_table_count(conn, table)
            ok = "OK" if cnt == exp else "MISMATCH"
            print(f"{table}: {cnt} / {exp} [{ok}]")
    finally:
        conn.close()
    s = load_status()
    print(f"Completed: {len(s['completed'])}/136, Errors: {len(s.get('errors', []))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-only", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=136)
    ap.add_argument("--apply-all", action="store_true")
    ap.add_argument("--mark-ok", type=str)
    ap.add_argument("--mark-err", nargs=2, metavar=("FILE", "MSG"))
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        print(json.dumps(load_status(), ensure_ascii=False, indent=2))
        return 0
    if args.mark_ok:
        mark_completed(args.mark_ok)
        return 0
    if args.mark_err:
        record_error(args.mark_err[0], args.mark_err[1])
        return 0
    if args.apply_all:
        db = os.getenv("DATABASE_URL", "").strip()
        if not db.startswith("postgres"):
            print("FAIL: DATABASE_URL required", file=sys.stderr)
            return 1
        return apply_all_direct(db)
    if args.emit_only:
        manifest = load_manifest()
        done = set(load_status().get("completed", []))
        out = []
        for e in manifest:
            if e["index"] < args.start:
                continue
            if len(out) >= args.count:
                break
            if e["file"] in done:
                continue
            out.append(emit_batch(e))
        print(json.dumps(out, ensure_ascii=False))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Process pending MCP migration payloads sequentially via Supabase execute_sql.

This script reads JSON payloads and SQL batch files, then executes each pending
batch. Intended for use with Supabase MCP or direct psycopg when DATABASE_URL
is available.

Usage:
  python run_mcp_migration_loop.py --dry-run
  python run_mcp_migration_loop.py --next          # print next pending payload
  python run_mcp_migration_loop.py --index 0       # print SQL for index 0
  DATABASE_URL=postgresql://... python run_mcp_migration_loop.py --apply-all
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"
BATCH_DIR = PROJECT_ROOT / "data" / "postgres_batches"
STATUS_FILE = PAYLOAD_DIR / "migration_status.json"
MANIFEST_FILE = PAYLOAD_DIR / "manifest.json"

SIZE_ERROR_MARKERS = (
    "payload too large",
    "query too long",
    "statement too long",
    "request entity too large",
    "max_allowed_packet",
)


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "errors": []}


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest() -> list[dict]:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def pending_entries() -> list[dict]:
    done = set(load_status().get("completed", []))
    return [e for e in load_manifest() if e["file"] not in done]


def load_sql(entry: dict) -> str:
    payload_path = PAYLOAD_DIR / entry["payload"]
    if payload_path.exists():
        return json.loads(payload_path.read_text(encoding="utf-8"))["sql"]
    return (BATCH_DIR / entry["file"]).read_text(encoding="utf-8")


def split_sql_at_rows(sql: str) -> tuple[str, str]:
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


def execute_with_split(conn, sql: str, filename: str) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    except Exception as exc:
        if not is_size_error(str(exc)):
            raise
        first, second = split_sql_at_rows(sql)
        print(f"SPLIT {filename}", file=sys.stderr)
        with conn.cursor() as cur:
            cur.execute(first)
            cur.execute(second)


def mark_completed(filename: str) -> None:
    status = load_status()
    if filename not in status["completed"]:
        status["completed"].append(filename)
    save_status(status)


def record_error(filename: str, msg: str) -> None:
    status = load_status()
    status.setdefault("errors", []).append({"file": filename, "error": msg})
    save_status(status)


def apply_all(database_url: str) -> int:
    pending = pending_entries()
    if not pending:
        print("No pending batches.")
        return 0
    conn = connect(database_url)
    try:
        for entry in pending:
            sql = load_sql(entry)
            filename = entry["file"]
            try:
                execute_with_split(conn, sql, filename)
                conn.commit()
                mark_completed(filename)
                print(f"OK {filename}")
            except Exception as exc:
                conn.rollback()
                record_error(filename, str(exc))
                print(f"ERROR {filename}: {exc}", file=sys.stderr)
                return 1
    finally:
        conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--index", type=int)
    parser.add_argument("--apply-all", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        pending = pending_entries()
        print(json.dumps(pending[:10], ensure_ascii=False, indent=2))
        print(f"TOTAL_PENDING={len(pending)}", file=sys.stderr)
        return 0

    if args.next:
        pending = pending_entries()
        if not pending:
            print("NONE")
            return 0
        e = pending[0]
        print(json.dumps({"index": e["index"], "file": e["file"], "table": e["table"], "bytes": e["bytes"]}))
        return 0

    if args.index is not None:
        manifest = load_manifest()
        entry = next(x for x in manifest if x["index"] == args.index)
        sys.stdout.write(load_sql(entry))
        return 0

    if args.apply_all:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url.startswith("postgres"):
            print("FAIL: set DATABASE_URL=postgresql://...", file=sys.stderr)
            return 1
        return apply_all(database_url)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

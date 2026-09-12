"""Apply one migration batch via Supabase MCP execute_sql (stdin: JSON with query result).

Usage from agent shell:
  python mcp_apply_one.py 0
  -> prints JSON: {"file": "...", "ok": true/false, "error": "..."}

Requires SUPABASE_MCP=1 env and agent calling execute_sql externally,
OR set DATABASE_URL for direct psycopg apply.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"
STATUS_FILE = PAYLOAD_DIR / "migration_status.json"
MANIFEST_FILE = PAYLOAD_DIR / "manifest.json"


def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "errors": []}


def save_status(status: dict) -> None:
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def get_entry(index: int) -> dict:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return next(x for x in manifest if x["index"] == index)


def load_sql(entry: dict) -> str:
    payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
    return payload["sql"]


def mark_ok(filename: str) -> None:
    s = load_status()
    if filename not in s["completed"]:
        s["completed"].append(filename)
    save_status(s)


def mark_err(filename: str, msg: str) -> None:
    s = load_status()
    s.setdefault("errors", []).append({"file": filename, "error": msg})
    save_status(s)


def apply_direct(index: int, database_url: str) -> dict:
    from apply_mcp_payloads import execute_with_split, connect

    entry = get_entry(index)
    filename = entry["file"]
    sql = load_sql(entry)
    conn = connect(database_url)
    try:
        execute_with_split(conn, sql, filename)
        conn.commit()
        mark_ok(filename)
        return {"index": index, "file": filename, "ok": True}
    except Exception as exc:
        conn.rollback()
        msg = str(exc)
        mark_err(filename, msg)
        return {"index": index, "file": filename, "ok": False, "error": msg}
    finally:
        conn.close()


def emit_sql(index: int) -> dict:
    entry = get_entry(index)
    return {"index": index, "file": entry["file"], "table": entry["table"], "sql": load_sql(entry)}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mcp_apply_one.py <index|pending|mark-ok|mark-err>", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "pending":
        done = set(load_status().get("completed", []))
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        pending = [e["index"] for e in manifest if e["file"] not in done]
        print(json.dumps(pending))
        return 0
    if cmd == "mark-ok":
        mark_ok(sys.argv[2])
        print(json.dumps({"ok": True, "file": sys.argv[2]}))
        return 0
    if cmd == "mark-err":
        mark_err(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "unknown")
        print(json.dumps({"ok": False, "file": sys.argv[2]}))
        return 0
    index = int(cmd)
    db = os.getenv("DATABASE_URL", "").strip()
    if db.startswith("postgres"):
        print(json.dumps(apply_direct(index, db), ensure_ascii=False))
        return 0
    print(json.dumps(emit_sql(index), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

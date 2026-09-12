"""Apply all MCP migration payloads via Supabase execute_sql (stdin JSON lines).

Each line: {"file": "...", "sql": "...", "ok": true/false, "error": "..."}
Used by agent to batch-read payloads; for direct apply use run_mcp_migration_loop.py --apply-all.
"""
from __future__ import annotations

import json
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


def mark_completed(filename: str) -> None:
    status = load_status()
    if filename not in status["completed"]:
        status["completed"].append(filename)
    save_status(status)


def record_error(filename: str, msg: str) -> None:
    status = load_status()
    status.setdefault("errors", []).append({"file": filename, "error": msg})
    save_status(status)


def get_batch(index: int) -> dict:
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    entry = next(x for x in manifest if x["index"] == index)
    payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
    return {"index": index, "file": entry["file"], "table": entry["table"], "sql": payload["sql"]}


def pending_indices() -> list[int]:
    done = set(load_status().get("completed", []))
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return [e["index"] for e in manifest if e["file"] not in done]


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if cmd == "pending":
        p = pending_indices()
        print(json.dumps(p))
        return 0
    if cmd == "get":
        idx = int(sys.argv[2])
        print(json.dumps(get_batch(idx), ensure_ascii=False))
        return 0
    if cmd == "mark":
        mark_completed(sys.argv[2])
        print(f"OK {sys.argv[2]}")
        return 0
    if cmd == "error":
        record_error(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "unknown")
        print(f"ERROR {sys.argv[2]}")
        return 0
    if cmd == "status":
        print(json.dumps(load_status(), ensure_ascii=False, indent=2))
        return 0
    raise SystemExit(f"unknown: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())

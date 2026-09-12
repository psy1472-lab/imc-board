"""Emit pending batches as JSON lines for MCP apply loop.

Usage:
  python mcp_emit_pending.py --start 0 --count 10
  -> one JSON object per line: {index, file, table, sql}
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=136)
    args = ap.parse_args()

    done = set(load_status().get("completed", []))
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    emitted = 0
    for entry in manifest:
        if entry["index"] < args.start:
            continue
        if entry["file"] in done:
            continue
        if emitted >= args.count:
            break
        payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
        out = {
            "index": entry["index"],
            "file": entry["file"],
            "table": entry["table"],
            "sql": payload["sql"],
        }
        print(json.dumps(out, ensure_ascii=False))
        emitted += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

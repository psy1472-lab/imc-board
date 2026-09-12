"""Combine pending batch SQL into chunks for fewer MCP execute_sql calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from apply_mcp_payloads import pending_entries, PAYLOAD_DIR  # noqa: E402
from mcp_agent_loop import ensure_sql_file  # noqa: E402

CHUNK_DIR = PAYLOAD_DIR / "_chunks"
MAX_BYTES = 90000


def build_chunks() -> list[dict]:
    CHUNK_DIR.mkdir(exist_ok=True)
    chunks: list[dict] = []
    current_sql: list[str] = []
    current_files: list[str] = []
    current_bytes = 0
    chunk_idx = 0

    def flush() -> None:
        nonlocal chunk_idx, current_sql, current_files, current_bytes
        if not current_sql:
            return
        sql = "\n".join(current_sql)
        out = CHUNK_DIR / f"chunk_{chunk_idx:03d}.sql"
        out.write_text(sql, encoding="utf-8")
        meta = {
            "chunk": chunk_idx,
            "files": current_files[:],
            "bytes": len(sql.encode("utf-8")),
            "sql_file": str(out),
        }
        (CHUNK_DIR / f"chunk_{chunk_idx:03d}.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        chunks.append(meta)
        chunk_idx += 1
        current_sql = []
        current_files = []
        current_bytes = 0

    for entry in pending_entries():
        sql_path = ensure_sql_file(entry)
        sql = sql_path.read_text(encoding="utf-8")
        size = len(sql.encode("utf-8"))
        if current_bytes + size > MAX_BYTES and current_sql:
            flush()
        current_sql.append(sql.rstrip().removesuffix(";") + ";")
        current_files.append(entry["file"])
        current_bytes += size

    flush()
    manifest = CHUNK_DIR / "manifest.json"
    manifest.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    return chunks


def main() -> int:
    chunks = build_chunks()
    print(json.dumps({"chunks": len(chunks), "files": sum(len(c["files"]) for c in chunks)}, ensure_ascii=False))
    for c in chunks:
        print(f"  chunk {c['chunk']}: {len(c['files'])} files, {c['bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

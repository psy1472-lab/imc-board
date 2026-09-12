"""Mark all files in a chunk as completed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from apply_mcp_payloads import mark_completed, PAYLOAD_DIR  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mcp_mark_chunk.py <chunk_index>", file=sys.stderr)
        return 1
    idx = int(sys.argv[1])
    meta = json.loads((PAYLOAD_DIR / "_chunks" / f"chunk_{idx:03d}.json").read_text(encoding="utf-8"))
    for fn in meta["files"]:
        mark_completed(fn)
    print(json.dumps({"ok": True, "chunk": idx, "marked": meta["files"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

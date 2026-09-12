"""Extract SQL for a batch index to stdout (raw SQL only, for MCP execute_sql)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"
MANIFEST_FILE = PAYLOAD_DIR / "manifest.json"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mcp_get_sql.py <index>", file=sys.stderr)
        return 1
    index = int(sys.argv[1])
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    entry = next(x for x in manifest if x["index"] == index)
    payload = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))
    sys.stdout.buffer.write(payload["sql"].encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

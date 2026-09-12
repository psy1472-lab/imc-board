"""Read one migration payload by index and print SQL for MCP execute_sql."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PAYLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "postgres_batches" / "_mcp_payloads"


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: run_mcp_migration_batch.py <index>", file=sys.stderr)
        raise SystemExit(1)
    idx = int(sys.argv[1])
    files = sorted(PAYLOAD_DIR.glob("*.json"))
    files = [f for f in files if not f.name.startswith("_")]
    if idx < 0 or idx >= len(files):
        print(f"FAIL: index {idx} out of range (0..{len(files)-1})", file=sys.stderr)
        raise SystemExit(1)
    data = json.loads(files[idx].read_text(encoding="utf-8"))
    # header line for logging
    print(f"FILE:{data['file']}", file=sys.stderr)
    print(f"TABLE:{data['table']}", file=sys.stderr)
    sys.stdout.write(data["sql"])


if __name__ == "__main__":
    main()

"""Export batch SQL files for MCP runner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_DIR = PROJECT_ROOT / "data" / "postgres_batches" / "_mcp_payloads"


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else start
    manifest = json.loads((PAYLOAD_DIR / "manifest.json").read_text(encoding="utf-8"))
    tmp = PAYLOAD_DIR / "_runner_tmp"
    tmp.mkdir(exist_ok=True)
    for e in manifest:
        if e["index"] < start or e["index"] > end:
            continue
        d = json.loads((PAYLOAD_DIR / e["payload"]).read_text(encoding="utf-8"))
        idx = f"{e['index']:04d}"
        (tmp / f"{idx}.meta.json").write_text(
            json.dumps({"index": e["index"], "file": e["file"], "table": e["table"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (tmp / f"{idx}.sql").write_text(d["sql"], encoding="utf-8")
    print(f"exported {start}-{end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

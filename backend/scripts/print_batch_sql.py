"""Print SQL for a manifest index (for MCP execute_sql)."""
import json
import sys
from pathlib import Path

PAYLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "postgres_batches" / "_mcp_payloads"
MANIFEST = PAYLOAD_DIR / "manifest.json"

idx = int(sys.argv[1])
entry = next(e for e in json.loads(MANIFEST.read_text(encoding="utf-8")) if e["index"] == idx)
sql = json.loads((PAYLOAD_DIR / entry["payload"]).read_text(encoding="utf-8"))["sql"]
sys.stderr.write(f"FILE:{entry['file']}\n")
sys.stdout.write(sql)

"""Export SQLite rows as Postgres INSERT batches for MCP execute_sql."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLITE_PATH = PROJECT_ROOT / "data" / "imc_dashboard.db"
OUT_DIR = PROJECT_ROOT / "data" / "postgres_batches"

TABLES = [
    ("report_metadata", 200),
    ("daily_summary", 100),
    ("hourly_throughput", 300),
    ("staffing", 300),
    ("quota_exchange", 200),
    ("transport_office", 300),
    ("sorting_machine", 200),
    ("safety_summary", 200),
    ("safety_incident", 200),
    ("anomaly", 200),
    ("validation_log", 200),
    ("kpi_comparison", 200),
    ("threshold_config", 50),
    ("operation_period", 50),
]

UPSERTS = {
    "report_metadata": """
        INSERT INTO report_metadata ({cols}) VALUES {values}
        ON CONFLICT (report_date) DO UPDATE SET
          center_name = EXCLUDED.center_name,
          report_format = EXCLUDED.report_format,
          day_type = EXCLUDED.day_type,
          file_path = EXCLUDED.file_path,
          ingested_at = EXCLUDED.ingested_at
    """,
    "daily_summary": """
        INSERT INTO daily_summary ({cols}) VALUES {values}
        ON CONFLICT (report_date) DO UPDATE SET
          center_name = EXCLUDED.center_name,
          national_volume = EXCLUDED.national_volume,
          total_volume = EXCLUDED.total_volume,
          dispatch_volume = EXCLUDED.dispatch_volume,
          arrival_volume = EXCLUDED.arrival_volume,
          remaining_volume = EXCLUDED.remaining_volume,
          productivity = EXCLUDED.productivity,
          ips_rate = EXCLUDED.ips_rate,
          last_operation_time = EXCLUDED.last_operation_time,
          communication_status = EXCLUDED.communication_status,
          raw_values = EXCLUDED.raw_values
    """,
    "threshold_config": """
        INSERT INTO threshold_config ({cols}) VALUES {values}
        ON CONFLICT (metric_name) DO UPDATE SET
          caution_min = EXCLUDED.caution_min,
          caution_max = EXCLUDED.caution_max,
          warning_min = EXCLUDED.warning_min,
          warning_max = EXCLUDED.warning_max,
          critical_min = EXCLUDED.critical_min,
          critical_max = EXCLUDED.critical_max
    """,
}


def _sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return f"'{json.dumps(value, ensure_ascii=False).replace(chr(39), chr(39)+chr(39))}'::jsonb"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    if text.startswith("{") or text.startswith("["):
        return f"'{text}'::jsonb"
    return f"'{text}'"


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _render_batch(table: str, cols: list[str], rows: list[sqlite3.Row]) -> str:
    col_sql = ", ".join(cols)
    values_sql = []
    for row in rows:
        literals = []
        for col in cols:
            value = row[col]
            if table == "daily_summary" and col == "raw_values" and value:
                value = json.loads(value) if isinstance(value, str) else value
            literals.append(_sql_literal(value))
        values_sql.append(f"({', '.join(literals)})")

    if table in UPSERTS:
        template = UPSERTS[table]
    elif table == "operation_period":
        template = "INSERT INTO operation_period ({cols}) VALUES {values}"
    else:
        template = "INSERT INTO {table} ({cols}) VALUES {values}"

    sql = template.format(table=table, cols=col_sql, values=", ".join(values_sql))
    return sql.strip()


def export() -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.sql"):
        old.unlink()

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    written: list[Path] = []

    for table, batch_size in TABLES:
        cols = _table_columns(conn, table)
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
        if not rows:
            continue
        for idx in range(0, len(rows), batch_size):
            batch = rows[idx : idx + batch_size]
            sql = _render_batch(table, cols, batch)
            path = OUT_DIR / f"{table}_{idx // batch_size:04d}.sql"
            path.write_text(sql, encoding="utf-8")
            written.append(path)
    conn.close()
    return written


if __name__ == "__main__":
    files = export()
    print(f"Wrote {len(files)} batch files to {OUT_DIR}")

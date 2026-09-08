"""SQLite 운영 DB를 Supabase Postgres로 일회성 마이그레이션합니다."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TABLES_COPY_ORDER = [
    ("report_metadata", ["report_date", "center_name", "report_format", "day_type", "file_path", "ingested_at"]),
    ("daily_summary", None),
    ("hourly_throughput", None),
    ("staffing", None),
    ("quota_exchange", None),
    ("transport_office", None),
    ("sorting_machine", None),
    ("safety_summary", None),
    ("safety_incident", None),
    ("anomaly", None),
    ("validation_log", None),
    ("kpi_comparison", None),
    ("threshold_config", None),
    ("operation_period", None),
]


def _connect_postgres(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("pip install psycopg[binary] required") from exc
    return psycopg.connect(database_url)


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def _copy_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    table: str,
    columns: list[str] | None,
) -> int:
    cols = columns or _table_columns(sqlite_conn, table)
    sqlite_conn.row_factory = sqlite3.Row
    rows = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["%s"] * len(cols))
    column_sql = ", ".join(cols)

    if table == "report_metadata":
        upsert = f"""
            INSERT INTO {table} ({column_sql})
            VALUES ({placeholders})
            ON CONFLICT (report_date) DO UPDATE SET
              center_name = EXCLUDED.center_name,
              report_format = EXCLUDED.report_format,
              day_type = EXCLUDED.day_type,
              file_path = EXCLUDED.file_path,
              ingested_at = EXCLUDED.ingested_at
        """
    elif table == "daily_summary":
        upsert = f"""
            INSERT INTO {table} ({column_sql})
            VALUES ({placeholders})
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
              raw_values = EXCLUDED.raw_values::jsonb
        """
    elif table == "threshold_config":
        upsert = f"""
            INSERT INTO {table} ({column_sql})
            VALUES ({placeholders})
            ON CONFLICT (metric_name) DO UPDATE SET
              caution_min = EXCLUDED.caution_min,
              caution_max = EXCLUDED.caution_max,
              warning_min = EXCLUDED.warning_min,
              warning_max = EXCLUDED.warning_max,
              critical_min = EXCLUDED.critical_min,
              critical_max = EXCLUDED.critical_max
        """
    elif table == "operation_period":
        upsert = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    else:
        pg_conn.execute(f"DELETE FROM {table}")
        upsert = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"

    count = 0
    with pg_conn.cursor() as cur:
        for row in rows:
            values = []
            for col in cols:
                value = row[col]
                if table == "daily_summary" and col == "raw_values" and value:
                    values.append(json.loads(value) if isinstance(value, str) else value)
                else:
                    values.append(value)
            cur.execute(upsert, values)
            count += 1
    return count


def migrate(sqlite_path: Path, database_url: str, *, dry_run: bool = False) -> int:
    if not sqlite_path.exists():
        print(f"FAIL: sqlite not found: {sqlite_path}")
        return 1

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    if dry_run:
        for table, _ in TABLES_COPY_ORDER:
            count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")
        return 0

    pg_conn = _connect_postgres(database_url)
    try:
        pg_conn.execute("BEGIN")
        totals: dict[str, int] = {}
        for table, columns in TABLES_COPY_ORDER:
            copied = _copy_table(sqlite_conn, pg_conn, table, columns)
            totals[table] = copied
            print(f"  {table}: {copied} rows")
        pg_conn.commit()
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        pg_conn.close()
        sqlite_conn.close()

    print(f"\nDone. report_metadata={totals.get('report_metadata', 0)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite IMC DB to Postgres")
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=PROJECT_ROOT / "data" / "imc_dashboard.db",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "").strip(),
        help="Postgres connection string (Supabase)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.database_url.startswith("postgres"):
        print("FAIL: set DATABASE_URL=postgresql://... or use --dry-run")
        raise SystemExit(1)

    raise SystemExit(migrate(args.sqlite, args.database_url, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

"""SQLite → Supabase Postgres migration via PostgREST (no DATABASE_URL required)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TABLES_COPY_ORDER = [
    ("report_metadata", ["report_date", "center_name", "report_format", "day_type", "file_path", "ingested_at"], "report_date"),
    ("daily_summary", None, "report_date"),
    ("hourly_throughput", None, None),
    ("staffing", None, None),
    ("quota_exchange", None, None),
    ("transport_office", None, None),
    ("sorting_machine", None, None),
    ("safety_summary", None, None),
    ("safety_incident", None, None),
    ("anomaly", None, None),
    ("validation_log", None, None),
    ("kpi_comparison", None, None),
    ("threshold_config", None, "metric_name"),
    ("operation_period", None, None),
]

DELETE_BEFORE_INSERT = {
    "hourly_throughput",
    "staffing",
    "quota_exchange",
    "transport_office",
    "sorting_machine",
    "safety_summary",
    "safety_incident",
    "anomaly",
    "validation_log",
    "kpi_comparison",
}


def _headers(api_key: str) -> dict[str, str]:
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def _row_dict(row: sqlite3.Row, cols: list[str], table: str) -> dict:
    out: dict = {}
    for col in cols:
        value = row[col]
        if table == "daily_summary" and col == "raw_values" and value:
            out[col] = json.loads(value) if isinstance(value, str) else value
        else:
            out[col] = value
    return out


def _delete_all(client: httpx.Client, base: str, table: str, headers: dict[str, str]) -> None:
    r = client.delete(f"{base}/rest/v1/{table}", params={"id": "neq.0"}, headers={**headers, "Prefer": "return=minimal"}, timeout=120.0)
    if r.status_code >= 400 and "id" in r.text:
        r = client.delete(
            f"{base}/rest/v1/{table}",
            params={"report_date": "neq.1900-01-01"},
            headers={**headers, "Prefer": "return=minimal"},
            timeout=120.0,
        )
    if r.status_code >= 400:
        r = client.post(
            f"{base}/rest/v1/rpc/truncate_imc_table",
            headers=headers,
            json={"table_name": table},
            timeout=120.0,
        )
        if r.status_code >= 400:
            print(f"  WARN: could not clear {table}: {r.status_code} {r.text[:200]}", file=sys.stderr)


def _upsert_batch(
    client: httpx.Client,
    base: str,
    table: str,
    rows: list[dict],
    headers: dict[str, str],
    *,
    batch_size: int = 100,
) -> int:
    count = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        r = client.post(
            f"{base}/rest/v1/{table}",
            headers=headers,
            json=chunk,
            timeout=120.0,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"{table} batch {i // batch_size}: {r.status_code} {r.text[:500]}")
        count += len(chunk)
    return count


def migrate(
    sqlite_path: Path,
    supabase_url: str,
    api_key: str,
    *,
    dry_run: bool = False,
    batch_size: int = 100,
) -> int:
    if not sqlite_path.exists():
        print(f"FAIL: sqlite not found: {sqlite_path}")
        return 1

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    if dry_run:
        for table, _, _ in TABLES_COPY_ORDER:
            count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count} rows")
        return 0

    base = supabase_url.rstrip("/")
    headers = _headers(api_key)
    totals: dict[str, int] = {}

    with httpx.Client() as client:
        for table, columns, _conflict in TABLES_COPY_ORDER:
            cols = columns or _table_columns(sqlite_conn, table)
            sqlite_rows = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
            if not sqlite_rows:
                totals[table] = 0
                print(f"  {table}: 0 rows")
                continue

            if table in DELETE_BEFORE_INSERT:
                _delete_all(client, base, table, headers)

            payload = [_row_dict(row, cols, table) for row in sqlite_rows]
            copied = _upsert_batch(client, base, table, payload, headers, batch_size=batch_size)
            totals[table] = copied
            print(f"  {table}: {copied} rows")

    sqlite_conn.close()
    print(f"\nDone. report_metadata={totals.get('report_metadata', 0)}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite IMC DB to Supabase via REST")
    parser.add_argument("--sqlite", type=Path, default=PROJECT_ROOT / "data" / "imc_dashboard.db")
    parser.add_argument("--supabase-url", default=os.getenv("SUPABASE_URL", "").strip())
    parser.add_argument("--api-key", default=os.getenv("SUPABASE_ANON_KEY", "").strip())
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.supabase_url or not args.api_key:
        print("FAIL: set SUPABASE_URL and SUPABASE_ANON_KEY, or pass --supabase-url / --api-key", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(migrate(args.sqlite, args.supabase_url, args.api_key, dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()

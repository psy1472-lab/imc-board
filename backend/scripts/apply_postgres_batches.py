"""Apply generated SQL batch files to Postgres via DATABASE_URL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH_DIR = PROJECT_ROOT / "data" / "postgres_batches"

TABLE_ORDER = [
    "report_metadata",
    "daily_summary",
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
    "threshold_config",
    "operation_period",
]


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("pip install psycopg[binary] required") from exc
    return psycopg.connect(database_url)


def apply_batches(batch_dir: Path, database_url: str, *, dry_run: bool = False) -> int:
    files: list[Path] = []
    for table in TABLE_ORDER:
        files.extend(sorted(batch_dir.glob(f"{table}_*.sql")))

    if not files:
        print(f"FAIL: no batch files in {batch_dir}")
        return 1

    if dry_run:
        for path in files:
            print(path.name)
        return 0

    conn = _connect(database_url)
    try:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            print(f"OK {path.name}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    verify = _connect(database_url)
    try:
        with verify.cursor() as cur:
            for table in TABLE_ORDER:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {table}: {count}")
    finally:
        verify.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Postgres SQL batch files")
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "").strip(),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.database_url.startswith("postgres"):
        print("FAIL: set DATABASE_URL=postgresql://...")
        raise SystemExit(1)

    raise SystemExit(apply_batches(args.batch_dir, args.database_url, dry_run=args.dry_run))


if __name__ == "__main__":
    main()

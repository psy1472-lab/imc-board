"""uploads 고아·파싱 실패 PDF만 재파싱 후 DB에 저장합니다."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend" / "src"))

from application.report_parser import ReportParser
from infrastructure.db.sqlite_repository import SqliteRepository

DB_PATH = BASE / "data" / "imc_dashboard.db"
UPLOADS_DIR = BASE / "data" / "uploads"
SKIP_FILES = {"test_min.pdf"}


def _targets() -> list[Path]:
    repository = SqliteRepository(str(DB_PATH))
    with repository._connect() as conn:
        db_paths = {
            Path(row["file_path"]).resolve()
            for row in conn.execute("SELECT file_path FROM report_metadata WHERE file_path IS NOT NULL")
            if row["file_path"]
        }

    pdfs = sorted(UPLOADS_DIR.glob("*.pdf")) if UPLOADS_DIR.exists() else []
    parser = ReportParser()
    targets: list[Path] = []

    for pdf in pdfs:
        if pdf.name in SKIP_FILES:
            continue
        if pdf.resolve() in db_paths:
            continue
        try:
            parser.parse(str(pdf))
            targets.append(pdf)
        except Exception:
            targets.append(pdf)

    return targets


def main() -> int:
    repository = SqliteRepository(str(DB_PATH))
    parser = ReportParser()
    targets = _targets()

    if not targets:
        print("No orphan or failed uploads to reingest.")
        return 0

    success = 0
    failed: list[tuple[str, str]] = []
    started = time.time()

    for index, pdf in enumerate(targets, start=1):
        try:
            report = parser.parse(str(pdf))
            repository.save_report(str(pdf), report)
            success += 1
            print(f"[OK] {pdf.name} -> {report.report_date.isoformat()}")
        except Exception as exc:  # noqa: BLE001
            failed.append((pdf.name, str(exc)))
            print(f"[FAIL] {pdf.name}: {exc}")

        if index % 10 == 0 or index == len(targets):
            elapsed = time.time() - started
            print(f"progress {index}/{len(targets)} success={success} failed={len(failed)} elapsed={elapsed:.1f}s")

    with repository._connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM report_metadata").fetchone()[0]

    print(f"done: success={success} failed={len(failed)} report_metadata={total}")
    if failed:
        print("failed samples:")
        for name, error in failed[:20]:
            print(f"  {name}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""381건 PDF 재파싱 및 DB 재적재."""
from __future__ import annotations

import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend" / "src"))

from application.report_parser import ReportParser
from infrastructure.db.sqlite_repository import SqliteRepository


def main() -> int:
    db_path = BASE / "data" / "imc_dashboard.db"
    repository = SqliteRepository(str(db_path))
    parser = ReportParser()

    with repository._connect() as conn:
        rows = conn.execute(
            "SELECT report_date, file_path FROM report_metadata ORDER BY report_date"
        ).fetchall()

    total = len(rows)
    success = 0
    failed: list[tuple[str, str]] = []
    hourly_warnings = 0
    hourly_pass = 0
    dispatch_fail = 0

    started = time.time()
    for index, row in enumerate(rows, start=1):
        report_date = row["report_date"]
        file_path = row["file_path"]
        if not Path(file_path).exists():
            failed.append((report_date, "file not found"))
            continue
        try:
            report = parser.parse(file_path)
            repository.save_report(file_path, report)
            success += 1
            for item in report.validation_logs:
                if item["rule_name"] == "hourly_sum_equals_total":
                    if item["status"] == "PASS":
                        hourly_pass += 1
                    else:
                        hourly_warnings += 1
                if item["rule_name"] == "dispatch_plus_arrival_equals_total" and item["status"] == "FAIL":
                    dispatch_fail += 1
        except Exception as exc:  # noqa: BLE001
            failed.append((report_date, str(exc)))

        if index % 25 == 0 or index == total:
            elapsed = time.time() - started
            print(
                f"[{index}/{total}] success={success} failed={len(failed)} "
                f"hourly_pass={hourly_pass} hourly_warn={hourly_warnings} "
                f"dispatch_fail={dispatch_fail} elapsed={elapsed:.1f}s"
            )

    print("\n=== Re-ingest complete ===")
    print(f"total={total} success={success} failed={len(failed)}")
    print(f"hourly_pass={hourly_pass} hourly_warning={hourly_warnings}")
    print(f"dispatch_fail={dispatch_fail}")
    if failed:
        print("failed samples:")
        for report_date, reason in failed[:10]:
            print(f"  {report_date}: {reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

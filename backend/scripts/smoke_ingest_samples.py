"""samples PDF ingest 스모크 테스트."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from application.report_parser import ReportParser
from infrastructure.db.sqlite_repository import SqliteRepository


def run_smoke(project_root: Path, db_path: Path) -> int:
    samples = sorted(project_root.glob("samples/*.pdf"))
    if not samples:
        print("FAIL: samples/*.pdf not found")
        return 1

    parser = ReportParser()
    repo = SqliteRepository(str(db_path))
    failures: list[str] = []

    for pdf_path in samples:
        try:
            report = parser.parse(str(pdf_path))
            repo.save_report(str(pdf_path), report)
            print(f"OK  {pdf_path.name} -> {report.report_date.isoformat()}")
        except Exception as exc:
            failures.append(f"{pdf_path.name}: {exc}")
            print(f"FAIL {pdf_path.name}: {exc}")

    print(f"\nTotal: {len(samples)}, OK: {len(samples) - len(failures)}, FAIL: {len(failures)}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="samples PDF ingest smoke test")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite path (default: <root>/data/smoke_test.db)",
    )
    args = parser.parse_args()
    db_path = args.db or (args.root / "data" / "smoke_test.db")
    raise SystemExit(run_smoke(args.root, db_path))


if __name__ == "__main__":
    main()

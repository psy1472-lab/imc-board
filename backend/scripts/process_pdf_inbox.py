"""data/inbox/ 신규 PDF를 로컬 DB·uploads·(선택) 프로덕션에 반영합니다."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from application.report_parser import ReportParser
from infrastructure.db.sqlite_repository import SqliteRepository


def _load_password_from_railway() -> str:
    raw = subprocess.check_output(
        ["railway", "variables", "--json"],
        text=True,
        cwd=PROJECT_ROOT,
    )
    password = json.loads(raw).get("IMC_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("IMC_ADMIN_PASSWORD not found in Railway variables")
    return password


def process_inbox(
    inbox_dir: Path,
    uploads_dir: Path,
    db_path: Path,
    processed_dir: Path,
    *,
    upload_production: bool = False,
    password: str | None = None,
) -> int:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(inbox_dir.glob("*.pdf"))
    if not pdfs:
        print("Inbox empty. Nothing to process.")
        return 0

    parser = ReportParser()
    repository = SqliteRepository(str(db_path))
    failures: list[str] = []
    processed = 0

    for pdf_path in pdfs:
        target = uploads_dir / pdf_path.name
        if target.exists():
            stem = pdf_path.stem
            suffix = pdf_path.suffix
            target = uploads_dir / f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"

        print(f"Processing {pdf_path.name} -> {target.name}", end=" ... ", flush=True)
        try:
            shutil.copy2(pdf_path, target)
            report = parser.parse(str(target))
            repository.save_report(str(target), report)
            archive_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf_path.name}"
            shutil.move(str(pdf_path), str(processed_dir / archive_name))
            processed += 1
            print(f"OK ({report.report_date.isoformat()})")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{pdf_path.name}: {exc}")
            print(f"FAIL ({exc})")

    print(f"\nLocal ingest: processed={processed} failed={len(failures)}")
    if failures:
        log_path = PROJECT_ROOT / "data" / "inbox_failures.txt"
        log_path.write_text("\n".join(failures), encoding="utf-8")
        print(f"Failures logged to {log_path}")
        return 1

    if upload_production and processed > 0:
        upload_script = PROJECT_ROOT / "backend" / "scripts" / "upload_production_pdfs.py"
        cmd = [
            sys.executable,
            str(upload_script),
            "--only-new",
            "--password",
            password or _load_password_from_railway(),
        ]
        print("\nUploading new report dates to production...")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            return result.returncode

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Process PDFs dropped in data/inbox")
    parser.add_argument(
        "--inbox",
        type=Path,
        default=PROJECT_ROOT / "data" / "inbox",
    )
    parser.add_argument(
        "--uploads",
        type=Path,
        default=PROJECT_ROOT / "data" / "uploads",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=PROJECT_ROOT / "data" / "imc_dashboard.db",
    )
    parser.add_argument(
        "--processed",
        type=Path,
        default=PROJECT_ROOT / "data" / "inbox" / "processed",
    )
    parser.add_argument(
        "--upload-production",
        action="store_true",
        help="After local ingest, upload only-new dates to production API",
    )
    parser.add_argument("--password", default=None)
    args = parser.parse_args()

    raise SystemExit(
        process_inbox(
            args.inbox,
            args.uploads,
            args.db,
            args.processed,
            upload_production=args.upload_production,
            password=(args.password.strip() if args.password else None),
        )
    )


if __name__ == "__main__":
    main()

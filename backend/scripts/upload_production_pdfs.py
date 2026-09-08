"""로컬 PDF를 프로덕션 Railway API로 업로드합니다."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import httpx

BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from application.report_parser import ReportParser

DEFAULT_API = "https://imc-dashboard-api-production-2929.up.railway.app"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_password_from_railway() -> str:
    raw = subprocess.check_output(
        ["railway", "variables", "--json"],
        text=True,
        cwd=PROJECT_ROOT,
    )
    variables = json.loads(raw)
    password = variables.get("IMC_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("IMC_ADMIN_PASSWORD not found in Railway variables")
    return password


def _admin_token(client: httpx.Client, api_base: str, password: str) -> str:
    response = client.post(
        f"{api_base}/api/admin/verify",
        json={"password": password},
        timeout=30.0,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("admin verify succeeded but token missing")
    return token


def _existing_dates(client: httpx.Client, api_base: str) -> set[str]:
    response = client.get(f"{api_base}/api/reports/dates", timeout=30.0)
    response.raise_for_status()
    return set(response.json().get("dates", []))


def _local_report_dates(db_path: Path) -> dict[str, str]:
    """Map absolute PDF path string -> report_date (ISO)."""
    if not db_path.exists():
        return {}
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT report_date, file_path
        FROM report_metadata
        WHERE file_path IS NOT NULL
        """
    ).fetchall()
    conn.close()
    mapping: dict[str, str] = {}
    for row in rows:
        if row["file_path"]:
            mapping[str(Path(row["file_path"]).resolve())] = row["report_date"]
    return mapping


def _filter_pdfs_by_existing(
    pdfs: list[Path],
    existing_dates: set[str],
    *,
    only_new: bool,
    local_db: Path | None = None,
) -> list[Path]:
    if not only_new:
        return pdfs

    local_dates = _local_report_dates(local_db) if local_db else {}
    parser = ReportParser()
    selected: list[Path] = []
    for pdf_path in pdfs:
        resolved = str(pdf_path.resolve())
        report_date = local_dates.get(resolved)
        if report_date is None:
            try:
                report_date = parser.parse(str(pdf_path)).report_date.isoformat()
            except Exception as exc:  # noqa: BLE001
                print(f"WARN parse skip {pdf_path.name}: {exc}")
                continue
        if report_date not in existing_dates:
            selected.append(pdf_path)
    return selected


def upload_pdfs(
    pdf_dir: Path,
    api_base: str,
    password: str,
    *,
    limit: int | None = None,
    skip_existing: bool = True,
    only_new: bool = False,
) -> int:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if limit is not None:
        pdfs = pdfs[:limit]

    if not pdfs:
        print(f"FAIL: no PDF files in {pdf_dir}")
        return 1

    failures: list[str] = []
    uploaded = 0
    skipped = 0

    with httpx.Client() as client:
        token = _admin_token(client, api_base, password)
        headers = {"Authorization": f"Bearer {token}"}
        existing = _existing_dates(client, api_base) if skip_existing or only_new else set()

        if only_new:
            before = len(pdfs)
            pdfs = _filter_pdfs_by_existing(
                pdfs,
                existing,
                only_new=True,
                local_db=PROJECT_ROOT / "data" / "imc_dashboard.db",
            )
            print(f"Only-new filter: {before} -> {len(pdfs)} file(s) to upload")

        if not pdfs:
            print("Nothing to upload.")
            return 0

        for index, pdf_path in enumerate(pdfs, start=1):
            print(f"[{index}/{len(pdfs)}] {pdf_path.name}", end=" ... ", flush=True)
            try:
                with pdf_path.open("rb") as handle:
                    response = client.post(
                        f"{api_base}/api/reports/upload",
                        headers=headers,
                        files={"file": (pdf_path.name, handle, "application/pdf")},
                        timeout=120.0,
                    )
                if response.status_code == 200:
                    body = response.json()
                    report_date = body.get("reportDate")
                    if report_date:
                        existing.add(report_date)
                    uploaded += 1
                    print(f"OK ({report_date})")
                    continue

                detail = response.text[:200]
                if skip_existing and response.status_code == 422 and "already" in detail.lower():
                    skipped += 1
                    print("SKIP (already ingested)")
                    continue

                failures.append(f"{pdf_path.name}: HTTP {response.status_code} {detail}")
                print(f"FAIL ({response.status_code})")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{pdf_path.name}: {exc}")
                print(f"FAIL ({exc})")

    print(
        f"\nDone. total={len(pdfs)} uploaded={uploaded} skipped={skipped} failed={len(failures)}"
    )
    if failures:
        log_path = PROJECT_ROOT / "data" / "production_upload_failures.txt"
        log_path.write_text("\n".join(failures), encoding="utf-8")
        print(f"Failures logged to {log_path}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload local PDFs to production API")
    parser.add_argument(
        "--dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "uploads",
        help="Directory containing PDF files",
    )
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument(
        "--password",
        default=None,
        help="Admin password (default: Railway IMC_ADMIN_PASSWORD)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max files to upload")
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="Parse PDFs locally and upload only report dates missing on production",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Upload even if report date already exists",
    )
    args = parser.parse_args()

    password = (args.password or _load_password_from_railway()).strip()
    raise SystemExit(
        upload_pdfs(
            args.dir,
            args.api.rstrip("/"),
            password,
            limit=args.limit,
            skip_existing=not args.no_skip_existing,
            only_new=args.only_new,
        )
    )


if __name__ == "__main__":
    main()

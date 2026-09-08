"""uploads 폴더와 DB 간 갭·파싱 실패를 분석합니다."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend" / "src"))

from application.report_parser import ReportParser

DB_PATH = BASE / "data" / "imc_dashboard.db"
UPLOADS_DIR = BASE / "data" / "uploads"
OUTPUT_PATH = BASE / "data" / "upload_gap_report.json"


def main() -> int:
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    meta_count = conn.execute("SELECT COUNT(*) FROM report_metadata").fetchone()[0]
    pdfs = sorted(UPLOADS_DIR.glob("*.pdf")) if UPLOADS_DIR.exists() else []

    db_paths = {
        Path(row["file_path"]).resolve()
        for row in conn.execute("SELECT file_path FROM report_metadata WHERE file_path IS NOT NULL")
        if row["file_path"]
    }
    orphan_pdfs = [p for p in pdfs if p.resolve() not in db_paths]

    parser = ReportParser()
    parse_failures: list[dict[str, str]] = []
    date_to_files: dict[str, list[str]] = {}

    for pdf in pdfs:
        try:
            report = parser.parse(str(pdf))
            date_to_files.setdefault(report.report_date.isoformat(), []).append(pdf.name)
        except Exception as exc:  # noqa: BLE001
            parse_failures.append(
                {
                    "fileName": pdf.name,
                    "filePath": str(pdf),
                    "error": str(exc),
                }
            )

    error_counts = Counter(item["error"].split("\n")[0][:120] for item in parse_failures)
    multi_date = {date_key: files for date_key, files in date_to_files.items() if len(files) > 1}

    report = {
        "reportMetadataCount": meta_count,
        "uploadPdfCount": len(pdfs),
        "gapUploadsMinusDb": len(pdfs) - meta_count,
        "orphanPdfCount": len(orphan_pdfs),
        "uniqueDatesFromUploads": len(date_to_files),
        "parseFailureCount": len(parse_failures),
        "datesWithMultiplePdfs": len(multi_date),
        "errorSummary": dict(error_counts),
        "parseFailures": parse_failures,
        "orphanFiles": [p.name for p in orphan_pdfs],
        "duplicateDateFiles": multi_date,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"report_metadata: {meta_count}")
    print(f"uploads/*.pdf: {len(pdfs)}")
    print(f"parse_failures: {len(parse_failures)}")
    print(f"orphan_pdfs: {len(orphan_pdfs)}")
    print(f"report written: {OUTPUT_PATH}")
    for error, count in error_counts.most_common(10):
        print(f"  {count}x {error}")
    return 0 if not parse_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

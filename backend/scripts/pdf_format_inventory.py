"""PDF 형식 인벤토리 — 평일/토·일/공휴일·compact 분류."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pdfplumber

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend" / "src"))

from domain.day_type import resolve_day_type
from infrastructure.pdf.format_detector import ReportFormatDetector
from infrastructure.pdf.reader import PdfDocument, PdfPage

_COMPACT_KPI = re.compile(r"소통물량\s*:\s*총")


def _read_first_page(path: str) -> tuple[PdfDocument, str, int]:
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
    document = PdfDocument(
        path=path,
        pages=[PdfPage(index=0, text=first_text, tables=[])],
    )
    return document, first_text, page_count


def _section_flags(text: str) -> dict[str, bool]:
    return {
        "hourly": "시간대별 처리" in text or "구 분 ~18" in text,
        "quota": "쿼터" in text and "교환" in text,
        "transport": "운송편" in text or "도 착 차 량" in text,
        "sorting": "소포구분기" in text,
        "safety": "안전보건" in text or "관리감독자" in text,
    }


def _write_markdown_summary(output: dict, md_path: Path) -> None:
    lines = [
        "# PDF 형식 매트릭스",
        "",
        f"- 총 보고서: **{output['total']}**",
        f"- 파일 존재: **{output['file_exists_count']}**",
        f"- DB·감지 불일치: **{len(output['db_detect_mismatches'])}**",
        "",
        "## 형식 × 일자유형",
        "",
        "| day_type:detected_format | 건수 |",
        "|---|---:|",
    ]
    for key, count in sorted(output["format_by_day_type"].items()):
        lines.append(f"| {key} | {count} |")
    lines.extend(
        [
            "",
            "## 요약",
            "",
            f"- standard: **{output['summary']['standard']}**",
            f"- compact: **{output['summary']['compact']}**",
            f"- holiday+compact (평일 요일 파일명 가능): **{output['summary']['holiday_compact']}**",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    db_only = "--db-only" in sys.argv
    db_path = BASE / "data" / "imc_dashboard.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT report_date, file_path, report_format FROM report_metadata ORDER BY report_date"
    ).fetchall()
    conn.close()

    detector = ReportFormatDetector()

    results: list[dict] = []
    format_by_day_type: Counter[str] = Counter()
    mismatches: list[dict] = []
    file_exists_count = 0
    standard_count = 0
    compact_count = 0
    holiday_compact_count = 0

    for row in rows:
        file_path = row["file_path"]
        report_date = date.fromisoformat(row["report_date"])
        day_type = resolve_day_type(report_date)
        entry: dict = {
            "report_date": row["report_date"],
            "day_type": day_type,
            "db_format": row["report_format"],
            "file_exists": bool(file_path and Path(file_path).exists()),
        }
        if not entry["file_exists"]:
            results.append(entry)
            continue

        file_exists_count += 1
        if db_only:
            detected = row["report_format"] or "unknown"
            entry["detected_format"] = detected
            entry["source"] = "db_metadata"
            format_by_day_type[f"{day_type}:{detected}"] += 1
            if detected == "standard":
                standard_count += 1
            elif detected == "compact":
                compact_count += 1
            if day_type == "holiday" and detected == "compact":
                holiday_compact_count += 1
            results.append(entry)
            continue

        try:
            document, text, page_count = _read_first_page(file_path)
            detected = detector.detect_profile(document).name
            if "소통물량" not in text and "소통실적" not in text:
                detected = "compact" if page_count <= 1 else "standard"
            entry["detected_format"] = detected
            entry["page_count"] = page_count
            entry["kpi_line"] = "소통물량" if _COMPACT_KPI.search(text) else "소통실적"
            entry["sections"] = _section_flags(text)
            format_by_day_type[f"{day_type}:{detected}"] += 1
            if detected == "standard":
                standard_count += 1
            else:
                compact_count += 1
            if day_type == "holiday" and detected == "compact":
                holiday_compact_count += 1
            if row["report_format"] and row["report_format"] != detected:
                mismatches.append(
                    {
                        "report_date": row["report_date"],
                        "db": row["report_format"],
                        "detected": detected,
                        "day_type": day_type,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)
        results.append(entry)

    output = {
        "total": len(rows),
        "source": "db_metadata" if db_only else "pdf_detection",
        "file_exists_count": file_exists_count,
        "format_by_day_type": dict(format_by_day_type),
        "db_detect_mismatches": mismatches,
        "summary": {
            "standard": standard_count,
            "compact": compact_count,
            "holiday_compact": holiday_compact_count,
        },
        "reports": results,
    }
    docs_dir = BASE / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    json_path = docs_dir / "pdf_format_matrix.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_summary(output, docs_dir / "pdf_format_matrix.md")
    print(f"Wrote {json_path}")
    print(f"Wrote {docs_dir / 'pdf_format_matrix.md'}")
    print("format_by_day_type:", format_by_day_type)
    print(f"mismatches: {len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

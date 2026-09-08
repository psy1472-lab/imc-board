"""남은 검증 이슈 상세 분석."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "backend" / "src"))

from application.report_parser import ReportParser
from infrastructure.pdf.extractors.daily_kpi import DailyKpiExtractor
from infrastructure.pdf.reader import PdfReader

DB = BASE / "data" / "imc_dashboard.db"
OUT = Path(__file__).resolve().parent / "issue_analysis.json"


def analyze_date(conn: sqlite3.Connection, report_date: str) -> dict:
    row = conn.execute(
        """
        SELECT ds.total_volume, ds.dispatch_volume, ds.arrival_volume,
               ds.remaining_volume, ds.raw_values,
               rm.file_path, rm.report_format
        FROM daily_summary ds
        JOIN report_metadata rm ON rm.report_date = ds.report_date
        WHERE ds.report_date = ?
        """,
        (report_date,),
    ).fetchone()
    if not row:
        return {"report_date": report_date, "error": "not found"}

    total, dispatch, arrival, remaining, raw_values, file_path, report_format = row
    hourly_sum = conn.execute(
        "SELECT SUM(total_volume) FROM hourly_throughput WHERE report_date = ?",
        (report_date,),
    ).fetchone()[0]

    validation = conn.execute(
        """
        SELECT rule_name, status, details FROM validation_log
        WHERE report_date = ? AND status IN ('FAIL', 'WARNING')
        """,
        (report_date,),
    ).fetchall()

    result: dict = {
        "report_date": report_date,
        "file_path": file_path,
        "report_format": report_format,
        "daily": {
            "total": total,
            "dispatch": dispatch,
            "arrival": arrival,
            "remaining": remaining,
            "dispatch_plus_arrival": (dispatch or 0) + (arrival or 0),
            "raw_values": json.loads(raw_values) if raw_values else {},
        },
        "hourly_sum": hourly_sum,
        "hourly_diff": (total or 0) - (hourly_sum or 0),
        "validation_issues": [
            {"rule": r[0], "status": r[1], "details": json.loads(r[2]) if r[2] else {}}
            for r in validation
        ],
    }

    if not Path(file_path).exists():
        result["pdf_error"] = "file not found"
        return result

    text = PdfReader().read(file_path).pages[0].text
    extractor = DailyKpiExtractor()
    section = extractor._extract_hourly_section(text)
    compact = extractor._is_compact_hourly_format(text)

    rows: dict[str, dict] = {}
    for row_type in ("dispatch", "arrival", "total"):
        match = extractor._match_hour_row(section, row_type)
        if not match:
            rows[row_type] = {"matched": False}
            continue
        raw = extractor._clean_hour_values(extractor._parse_hour_row(match.group(1)))
        aligned = extractor._align_hour_values(
            raw,
            match.group(2) if match.lastindex and match.lastindex >= 2 else None,
            sparse=compact and row_type != "total",
        )
        rows[row_type] = {
            "matched": True,
            "raw_len": len(raw),
            "raw": raw,
            "aligned": aligned,
            "row_total": match.group(2) if match.lastindex and match.lastindex >= 2 else None,
            "snippet": match.group(0)[:120],
        }

    result["hourly_parse"] = rows
    result["compact_format"] = compact

    # 시간대별 DB 상세
    hourly_db = conn.execute(
        """
        SELECT hour_slot, dispatch_volume, arrival_volume, total_volume
        FROM hourly_throughput
        WHERE report_date = ?
        ORDER BY hour_slot
        """,
        (report_date,),
    ).fetchall()
    result["hourly_db"] = [
        {"slot": r[0], "dispatch": r[1], "arrival": r[2], "total": r[3]}
        for r in hourly_db
        if (r[3] or 0) > 0 or r[1] or r[2]
    ]

    # 소통실적 KPI 텍스트
    kpi_match = re.search(r"소통실적\s*:[^\n]+", text) or re.search(
        r"소통물량\s*:[^\n]+", text
    )
    result["kpi_line"] = kpi_match.group(0) if kpi_match else None

    # 재파싱 검증
    try:
        report = ReportParser().parse(file_path)
        result["reparsed_validation"] = report.validation_logs
        result["reparsed_hourly_sum"] = sum(x.total_volume or 0 for x in report.hourly_throughput)
    except Exception as exc:  # noqa: BLE001
        result["reparsed_error"] = str(exc)

    # 구분기 (FAIL 건용)
    sorting = conn.execute(
        "SELECT total_supply, total_sorted, sorting_rate FROM sorting_machine WHERE report_date = ?",
        (report_date,),
    ).fetchone()
    if sorting:
        result["sorting"] = {
            "supply": sorting[0],
            "sorted": sorting[1],
            "rate": sorting[2],
        }

    quota = conn.execute(
        "SELECT quarter_standard, quarter_actual, quarter_difference FROM quota_exchange WHERE report_date = ?",
        (report_date,),
    ).fetchone()
    if quota and quota[0]:
        result["quota"] = dict(
            zip(["standard", "actual", "difference"], quota, strict=True)
        )

    return result


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # 대형 시간대 오차
    large_diff = conn.execute(
        """
        SELECT ds.report_date, ds.total_volume, SUM(ht.total_volume) AS hourly_total,
               ds.total_volume - SUM(ht.total_volume) AS diff
        FROM daily_summary ds
        JOIN hourly_throughput ht ON ht.report_date = ds.report_date
        GROUP BY ds.report_date
        HAVING ABS(ds.total_volume - SUM(ht.total_volume)) > 50000
        ORDER BY ABS(diff) DESC
        """
    ).fetchall()

    # FAIL 건
    fail_dates = conn.execute(
        """
        SELECT DISTINCT report_date FROM validation_log
        WHERE status = 'FAIL'
        ORDER BY report_date
        """
    ).fetchall()

    target_dates = sorted(
        {r["report_date"] for r in large_diff} | {r["report_date"] for r in fail_dates}
    )

    analysis = {
        "large_hourly_diff": [
            {
                "report_date": r["report_date"],
                "total": r["total_volume"],
                "hourly_sum": r["hourly_total"],
                "diff": r["diff"],
            }
            for r in large_diff
        ],
        "fail_dates": [r["report_date"] for r in fail_dates],
        "details": [analyze_date(conn, d) for d in target_dates],
    }

    OUT.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(analysis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

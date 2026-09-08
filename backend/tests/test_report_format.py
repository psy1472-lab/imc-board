from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from application.report_parser import ReportParser
from domain.day_type import resolve_day_type
from domain.format_profile import COMPACT_PROFILE, STANDARD_PROFILE
from fixtures.compact_reports import (
    HOLIDAY_COMPACT_SNIPPET,
    SATURDAY_COMPACT_SNIPPET,
    SUNDAY_COMPACT_SNIPPET,
)
from infrastructure.pdf.format_detector import ReportFormatDetector
from infrastructure.pdf.reader import PdfDocument, PdfPage


def _document(text: str, path: str = "fixture.pdf") -> PdfDocument:
    return PdfDocument(path=path, pages=[PdfPage(index=0, text=text, tables=[])])


def test_resolve_day_type_weekend_and_holiday():
    assert resolve_day_type(date(2026, 4, 25)) == "saturday"
    assert resolve_day_type(date(2026, 4, 26)) == "sunday"
    assert resolve_day_type(date(2025, 10, 6)) == "holiday"
    assert resolve_day_type(date(2025, 1, 31)) == "weekday"


def test_holiday_weekday_filename_still_compact_format():
    detector = ReportFormatDetector()
    profile = detector.detect_profile(_document(HOLIDAY_COMPACT_SNIPPET))
    assert profile.name == "compact"
    assert resolve_day_type(date(2025, 10, 6)) == "holiday"


def test_detector_uses_standard_section_headings():
    detector = ReportFormatDetector()
    text = (
        "소통실적 없음\n"
        "시간대별 처리 및 인력투입 현황\n"
        "교환 및 수지 쿼터 준수현황\n"
    )
    profile = detector.detect_profile(_document(text, "ambiguous.pdf"))
    assert profile.name == "standard"


def test_saturday_compact_kpi_extraction():
    from infrastructure.pdf.extractors.daily_kpi import DailyKpiExtractor

    extractor = DailyKpiExtractor()
    report_date, _, summary = extractor.extract(_document(SATURDAY_COMPACT_SNIPPET))
    assert report_date == date(2026, 4, 25)
    assert summary.total_volume == 30200
    assert summary.dispatch_volume == 28400
    assert summary.arrival_volume == 4100


def test_report_parser_compact_skips_standard_sections():
    parser = ReportParser()
    document = _document(SUNDAY_COMPACT_SNIPPET, "sunday.pdf")
    with patch.object(parser.reader, "read", return_value=document):
        report = parser.parse("sunday.pdf")

    assert report.report_format == "compact"
    assert report.day_type == "sunday"
    assert report.quota_exchange is None
    assert report.transport_offices == []
    assert report.safety_categories == []
    assert report.daily_summary.total_volume == 31581
    assert any(log["rule_name"] == "dispatch_plus_arrival_equals_total" for log in report.validation_logs)
    dispatch_log = next(
        log for log in report.validation_logs if log["rule_name"] == "dispatch_plus_arrival_equals_total"
    )
    assert dispatch_log["status"] == "WARNING"
    assert dispatch_log.get("profile") == "compact"


def test_report_parser_holiday_compact_day_type():
    parser = ReportParser()
    document = _document(HOLIDAY_COMPACT_SNIPPET, "holiday.pdf")
    with patch.object(parser.reader, "read", return_value=document):
        report = parser.parse("holiday.pdf")

    assert report.report_format == "compact"
    assert report.day_type == "holiday"
    assert report.report_date == date(2025, 10, 6)


def test_format_profiles_sections():
    assert "quota" in STANDARD_PROFILE.sections_available
    assert "quota" not in COMPACT_PROFILE.sections_available
    assert COMPACT_PROFILE.validation_profile == "compact"

from __future__ import annotations

from datetime import date

from domain.entities import DailySummary, HourlyThroughput, ParsedReport, SortingMachine
from domain.format_profile import COMPACT_PROFILE, STANDARD_PROFILE
from infrastructure.pdf.extractors.daily_kpi import DailyKpiExtractor
from infrastructure.pdf.reader import PdfDocument, PdfPage
from infrastructure.validator import DataValidator


COMPACT_HOURLY_SNIPPET = """
소통물량 : 총 31,581개 (발송 29,721 배분 4,512) (단위: 개)
구 분 ~18 18~ 19~ 20~ 21~ 22~ 23~ 0~ 1~ 2~ 3~ 4~ 5~ 6~ 합계
발 송 1.5 1.2 0.3 3
배 분 0.1 0.1 0.2
소 계 0 0 1.5 1.2 0.3 0.1 0.1 0 0 0 0 0 0 0 3.2
"""


def _compact_document() -> PdfDocument:
    return PdfDocument(path="compact.pdf", pages=[PdfPage(index=0, text=COMPACT_HOURLY_SNIPPET, tables=[])])


def test_format_detector_uses_kpi_keyword():
    from infrastructure.pdf.format_detector import ReportFormatDetector

    compact = _compact_document()
    standard = PdfDocument(
        path="standard.pdf",
        pages=[PdfPage(index=0, text="소통실적 : 60.8만개(발송:43.3만개, 도착:17.5만개, 잔량: 없음)", tables=[])],
    )
    detector = ReportFormatDetector()
    assert detector.detect_profile(compact).name == "compact"
    assert detector.detect_profile(standard).name == "standard"


def test_strip_compact_row_subtotal():
    extractor = DailyKpiExtractor()
    assert extractor._strip_compact_row_subtotal(["1.5", "1.2", "0.3", "3"], None) == ["1.5", "1.2", "0.3"]
    assert extractor._strip_compact_row_subtotal(["0.1", "0.1", "0.2"], None) == ["0.1", "0.1"]


def test_hourly_dispatch_from_truncated_table_cell():
    """09-08처럼 표 셀이 '리 발송'으로 잘려도 만개 행을 발송으로 읽는다."""
    table_cell = (
        "리 발송 - 2.2 3.4 2.9 3.6 3.3 4.4 4.9 1.3 - - - - - 26.0\n"
        "량 도착 1.0 - - - - - - - 1.6 4.0 3.5 1.3 0.2 - 11.6\n"
        "위:만개) 계 1.0 2.2 3.4 2.9 3.6 3.3 4.4 4.9 2.9 4.0 3.5 1.3 0.2 - 37.6"
    )
    document = PdfDocument(
        path="26.09.08.pdf",
        pages=[
            PdfPage(
                index=0,
                text=(
                    "시간대별 처리 및 인력투입 현황\n"
                    "구 분 ~18 18~ 19~ 20~ 21~ 22~ 23~ 0~ 1~ 2~ 3~ 4~ 5~ 6~ 합계\n"
                    "발송 35 33 29 23 13 4 - - - - - - - - 137\n"
                ),
                tables=[[[None, None, table_cell]]],
            )
        ],
    )
    hourly, _ = DailyKpiExtractor().extract_hourly(document, date(2026, 9, 8))
    by_slot = {item.hour_slot: item for item in hourly}
    assert by_slot["18"].dispatch_volume == 22000
    assert by_slot["00"].dispatch_volume == 49000
    assert by_slot["~18"].arrival_volume == 10000
    assert by_slot["02"].arrival_volume == 40000
    assert sum(item.dispatch_volume or 0 for item in hourly) == 260000
    assert sum(item.arrival_volume or 0 for item in hourly) == 116000


def test_hourly_omitted_dashes_and_staffing_from_2025_01_02():
    """01-02처럼 빈 칸 대시가 생략되면 발송은 앞, 도착은 뒤에 맞춘다."""
    table_cell = (
        "구 분 ~18 18~ 19~ 20~ 21~ 22~ 23~ 0~ 1~ 2~ 3~ 4~ 5~ 6~ 합계\n"
        "처리 발송 (단위:만개) 발송 0.4 3.8 4.5 4.9 4.9 4.3 5.6 5.5 2.7 36.6\n"
        "도착 1.6 5.6 4.6 0.9 0.1 12.8\n"
        "계 0.4 3.8 4.5 4.9 4.9 4.3 5.6 5.5 4.3 5.6 4.6 0.9 0.1 49.4\n"
        "실제근무 인력(⑦-⑧+⑨+⑩-⑪)(명) 6 174 248 248 248 115 217 288 286 255 260 189 23\n"
        "인시당 처리물량(처리물량/⑪)(개) 220 182 200 196 370 256 190 152 218 178 46 49\n"
    )
    document = PdfDocument(
        path="25.01.02.pdf",
        pages=[
            PdfPage(
                index=0,
                text=(
                    "시간대별 처리 및 인력투입 현황 (평균 인시당 처리 물량: 193.23)\n"
                    "구 분 ~18 18~ 19~ 20~ 21~ 22~ 23~ 0~ 1~ 2~ 3~ 4~ 5~ 6~ 합계\n"
                ),
                tables=[[[None, None, table_cell]]],
            )
        ],
    )
    hourly, staffing = DailyKpiExtractor().extract_hourly(document, date(2025, 1, 2))
    by_slot = {item.hour_slot: item for item in hourly}
    staff_by_slot = {item.hour_slot: item for item in staffing}
    assert by_slot["~18"].dispatch_volume == 4000
    assert by_slot["~18"].arrival_volume is None
    assert by_slot["01"].dispatch_volume == 27000
    assert by_slot["01"].arrival_volume == 16000
    assert by_slot["01"].total_volume == 43000
    assert by_slot["05"].arrival_volume == 1000
    assert by_slot["06"].total_volume is None
    assert sum(item.total_volume or 0 for item in hourly) == 494000
    assert staff_by_slot["~18"].actual_staff == 6
    assert staff_by_slot["18"].actual_staff == 174
    assert staff_by_slot["18"].productivity == 220
    assert staff_by_slot["06"].actual_staff is None

    _, _, summary = DailyKpiExtractor().extract(
        PdfDocument(
            path="25.01.02.pdf",
            pages=[
                PdfPage(
                    index=0,
                    text=(
                        "중부권IMC 일일소통현황 보고('25.01.02.목)\n"
                        "소통실적 : 49.4만개 (발송 36.6만개, 도착 12.8만개, 잔량 0.0만개)\n"
                        "시간대별 처리 및 인력투입 현황 (평균 인시당 처리 물량: 193.23)\n"
                    ),
                    tables=[],
                )
            ],
        )
    )
    assert summary.productivity == 193.23


def test_compact_hourly_alignment():
    extractor = DailyKpiExtractor()
    hourly, _ = extractor.extract_hourly(_compact_document(), date(2026, 4, 26), profile=COMPACT_PROFILE)
    by_slot = {item.hour_slot: item for item in hourly}
    assert by_slot["19"].dispatch_volume == 15000
    assert by_slot["20"].dispatch_volume == 12000
    assert by_slot["21"].dispatch_volume == 3000
    assert by_slot["22"].arrival_volume == 1000
    assert by_slot["23"].arrival_volume == 1000


def test_validator_compact_dispatch_warning_not_fail():
    report = ParsedReport(
        report_date=date(2026, 4, 26),
        center_name="중부권IMC",
        report_format="compact",
        daily_summary=DailySummary(
            report_date=date(2026, 4, 26),
            dispatch_volume=29721,
            arrival_volume=4512,
            total_volume=31581,
        ),
        hourly_throughput=[
            HourlyThroughput(date(2026, 4, 26), "19", total_volume=15000),
            HourlyThroughput(date(2026, 4, 26), "20", total_volume=13000),
        ],
    )
    logs = DataValidator().validate(report)
    by_rule = {item["rule_name"]: item["status"] for item in logs}
    assert by_rule["dispatch_plus_arrival_equals_total"] == "WARNING"
    assert all(log.get("profile") == "compact" for log in logs)


def test_align_hour_values_skips_prefix_and_subtotal():
    extractor = DailyKpiExtractor()
    values = [
        "0.8",
        "5.8",
        "5.9",
        "6.7",
        "6.7",
        "6.3",
        "6.3",
        "3.7",
        "1.1",
        None,
        None,
        None,
        None,
        None,
        "43.3",
    ]
    aligned = extractor._align_hour_values(extractor._clean_hour_values(values), "2")
    assert aligned[0] == "0.8"
    assert aligned[1] == "5.8"
    assert aligned[-1] is None
    assert "43.3" not in aligned


def test_align_hour_values_keeps_fourteen_hour_columns():
    extractor = DailyKpiExtractor()
    values = ["0.5", "3.6", "4.9", "5.2", "5.0", "4.8", "5.9", "4.1", "2.6", "0.1", None, None, None, None]
    aligned = extractor._align_hour_values(extractor._clean_hour_values(values), "36.7")
    assert len(aligned) == 14
    assert aligned[0] == "0.5"
    assert aligned[1] == "3.6"


def test_validator_dispatch_plus_arrival_pass():
    report = ParsedReport(
        report_date=date(2025, 1, 31),
        center_name="중부권IMC",
        report_format="standard",
        daily_summary=DailySummary(
            report_date=date(2025, 1, 31),
            dispatch_volume=433000,
            arrival_volume=175000,
            total_volume=608000,
        ),
        hourly_throughput=[
            HourlyThroughput(date(2025, 1, 31), "18", total_volume=58000),
            HourlyThroughput(date(2025, 1, 31), "19", total_volume=59000),
        ],
        sorting_machine=SortingMachine(date(2025, 1, 31), total_supply=100, total_sorted=90),
    )
    logs = DataValidator().validate(report)
    by_rule = {item["rule_name"]: item["status"] for item in logs}
    assert by_rule["dispatch_plus_arrival_equals_total"] == "PASS"
    assert by_rule["sorted_lte_supply"] == "PASS"


def test_parse_quota_row_with_round_column():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor

    text = (
        "교환 및 수지 쿼터 준수현황\n"
        "구분 기준대수 (사전협의 추가) 제주D+2 기타(조달센터등) 초과 계 회차\n"
        "쿼터 117 0 0 1 -7 110 0\n"
        "교환 129 - -12 117 0\n"
    )
    extractor = QuotaExchangeExtractor()
    standard, actual, difference = extractor._parse_quota_row(text, "쿼터")
    assert standard == 117
    assert actual == 110
    assert difference == -7

    exchange_standard, exchange_actual, exchange_difference = extractor._parse_quota_row(text, "교환")
    assert exchange_standard == 129
    assert exchange_actual == 117
    assert exchange_difference == -12


def test_parse_quota_row_extended_format():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor

    text = (
        "교환 및 수지 쿼터 준수현황\n"
        "구분 기준대수 사전협의 추가 제주D+2 기타(조달센터 등) 초과 계 회차\n"
        "쿼터 105 - 3 1 -25 80\n"
        "교환 129 - -22 107\n"
    )
    extractor = QuotaExchangeExtractor()
    standard, actual, difference = extractor._parse_quota_row(text, "쿼터")
    assert standard == 105
    assert actual == 185
    assert difference == 80

    exchange_standard, exchange_actual, exchange_difference = extractor._parse_quota_row(text, "교환")
    assert exchange_standard == 129
    assert exchange_actual == 107
    assert exchange_difference == -22


def test_parse_quota_row_spaced_header_and_seven_columns():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor

    text = (
        "교환 및 수지 쿼 터 준 수 현 황\n"
        "구분 ①기준대수 ⑤제주D+2 ⑥기타(조달센터 등)\n"
        "쿼터 106 - 99 -7 0 1 100\n"
        "교환 129 - 121 -8\n"
        "배분 및 교환 마지막 운송편 발송 현황\n"
    )
    extractor = QuotaExchangeExtractor()
    standard, actual, difference = extractor._parse_quota_row(text, "쿼터")
    assert standard == 106
    assert actual == 100
    assert difference == -7

    exchange_standard, exchange_actual, exchange_difference = extractor._parse_quota_row(text, "교환")
    assert exchange_standard == 129
    assert exchange_actual == 121
    assert exchange_difference == -8


def test_parse_int_treats_dash_as_zero():
    from infrastructure.normalizer import parse_int, parse_volume, parse_volume_with_peer_man_context, to_int_or_zero

    assert parse_int("-") == (0, "-")
    assert parse_volume("-") == (0, "-")
    assert to_int_or_zero("-") == 0


def test_parse_volume_total_typo_as_man_when_peers_use_man():
    from infrastructure.normalizer import parse_volume_with_peer_man_context

    normalized, raw = parse_volume_with_peer_man_context("29.1개", peers_use_man_unit=True)
    assert raw == "29.1개"
    assert normalized == 291000


def test_parse_quota_row_inline_label_and_four_numeric_exchange():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor

    text = (
        "교환 및 수지 쿼 터 준 수 현 황\n"
        "- 쿼터 90 2 93 1 1 1 95\n"
        "교환 125 1 120 -6\n"
        "소통실적 : 37.6만개 *교환 잔량: 없음\n"
        "배분 및 교환 마지막 운송편 발송 현황\n"
    )
    extractor = QuotaExchangeExtractor()
    standard, actual, difference = extractor._parse_quota_row(text, "쿼터")
    assert standard == 90
    assert actual == 95
    assert difference == 1

    exchange_standard, exchange_actual, exchange_difference = extractor._parse_quota_row(text, "교환")
    assert exchange_standard == 125
    assert exchange_actual == 120
    assert exchange_difference == -6


def test_extract_quota_from_first_page_and_transport_from_attachment():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor, TransportExtractor

    document = PdfDocument(
        path="26.09.08.pdf",
        pages=[
            PdfPage(
                index=0,
                text=(
                    "교환 및 수지 쿼 터 준 수 현 황\n"
                    "- 쿼터 90 2 93 1 1 1 95\n"
                    "교환 125 1 120 -6\n"
                    "*교환 잔량: 없음\n"
                    "배분 및 교환 마지막 운송편 발송 현황\n"
                ),
                tables=[],
            ),
            PdfPage(
                index=1,
                text="【붙임1】집중국별 쿼 터 발 송 현 황\n동서울집 7,852 4 4 4 0 23:53 68\n",
                tables=[],
            ),
            PdfPage(index=2, text="소포구분기 가동현황\n", tables=[]),
        ],
    )
    quota = QuotaExchangeExtractor().extract(document, date(2026, 9, 8))
    assert quota.quarter_standard == 90
    assert quota.quarter_actual == 95
    assert quota.exchange_standard == 125
    assert quota.exchange_actual == 120
    assert quota.exchange_remaining == 0

    offices = TransportExtractor().extract(document, date(2026, 9, 8))
    assert len(offices) == 1
    assert offices[0].office_name == "동서울집"
    assert offices[0].vehicles_actual == 4
    assert offices[0].vehicles_standard == 4


def test_extract_maritime_offices_with_dash_quota():
    from infrastructure.pdf.extractors.operations import TransportExtractor

    document = PdfDocument(
        path="26.09.08.pdf",
        pages=[
            PdfPage(index=0, text="소통실적", tables=[]),
            PdfPage(
                index=1,
                text=(
                    "【붙임1】집중국별 쿼 터 발 송 현 황\n"
                    "동서울집 7,852 4 4 4 0 23:53 68\n"
                    "인천해상 - - 인천해상 599 2 599 2 - - 2 15:09 24\n"
                    "평택해상 평택특송 632 1 632 1 - - 1 21:24 3\n"
                ),
                tables=[],
            ),
        ],
    )
    by_name = {item.office_name: item for item in TransportExtractor().extract(document, date(2026, 9, 8))}
    assert by_name["인천해상"].vehicles_actual == 2
    assert by_name["인천해상"].vehicles_standard == 0
    assert by_name["인천해상"].volume == 599
    assert by_name["인천해상"].status == "WARNING"
    assert by_name["평택해상"].vehicles_actual == 1
    assert by_name["평택해상"].vehicles_standard == 0
    assert by_name["평택해상"].status == "WARNING"


def test_parse_quota_row_with_dash_cells():
    from infrastructure.pdf.extractors.operations import QuotaExchangeExtractor

    text = (
        "교환 및 수지 쿼터 준수현황\n"
        "구분 ①기준대수 ⑤제주D+2 ⑥기타\n"
        "쿼터 106 - 99 - 0 1 100\n"
    )
    extractor = QuotaExchangeExtractor()
    standard, actual, difference = extractor._parse_quota_row(text, "쿼터")
    assert standard == 106
    assert actual == 100
    assert difference == 0


def test_extract_standard_kpi_spaced_format():
    from tests.fixtures.failed_upload_snippets import STANDARD_KPI_SPACED

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.01.02.pdf",
        pages=[PdfPage(index=0, text=STANDARD_KPI_SPACED, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 1, 2)
    assert summary.total_volume == 494000
    assert summary.dispatch_volume == 366000
    assert summary.arrival_volume == 128000
    assert summary.remaining_volume == 0


def test_extract_standard_kpi_bunbunjanryang():
    from tests.fixtures.failed_upload_snippets import STANDARD_KPI_BUNBUNJANRYANG

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.08.18.pdf",
        pages=[PdfPage(index=0, text=STANDARD_KPI_BUNBUNJANRYANG, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 8, 18)
    assert summary.total_volume == 602000
    assert summary.remaining_volume == 30000


def test_extract_standard_kpi_total_typo():
    from tests.fixtures.failed_upload_snippets import STANDARD_KPI_TOTAL_TYPO

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.03.28.pdf",
        pages=[PdfPage(index=0, text=STANDARD_KPI_TOTAL_TYPO, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 3, 28)
    assert summary.total_volume == 291000  # PDF '29.1개' → 29.1만개
    assert summary.dispatch_volume == 208000
    assert summary.arrival_volume == 83000
    assert summary.raw_values["total_volume"] == "29.1개"


def test_extract_compact_kpi_slash_separator():
    from tests.fixtures.failed_upload_snippets import COMPACT_KPI_SLASH

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.11.23.pdf",
        pages=[PdfPage(index=0, text=COMPACT_KPI_SLASH, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 11, 23)
    assert summary.total_volume == 40068
    assert summary.dispatch_volume == 34671
    assert summary.arrival_volume == 5397
    assert summary.remaining_volume == 0


def test_extract_standard_kpi_no_remaining_field():
    from tests.fixtures.failed_upload_snippets import STANDARD_KPI_NO_REMAINING

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.08.20.pdf",
        pages=[PdfPage(index=0, text=STANDARD_KPI_NO_REMAINING, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 8, 20)
    assert summary.total_volume == 326000
    assert summary.remaining_volume == 30000


def test_extract_title_date_with_spaces():
    from tests.fixtures.failed_upload_snippets import TITLE_DATE_SPACED

    extractor = DailyKpiExtractor()
    document = PdfDocument(
        path="25.01.15.pdf",
        pages=[PdfPage(index=0, text=TITLE_DATE_SPACED, tables=[])],
    )
    report_date, _, summary = extractor.extract(document)
    assert report_date == date(2025, 1, 15)
    assert summary.total_volume == 449000

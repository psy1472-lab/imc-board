from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.pdf.extractors.operations import SafetyCheckExtractor
from infrastructure.pdf.reader import PdfDocument, PdfPage


def _document(text: str, tables=None) -> PdfDocument:
    return PdfDocument(
        path="safety.pdf",
        pages=[PdfPage(index=0, text=text, tables=tables or [])],
    )


def test_incident_from_table_ignores_adjacent_dispatch_columns():
    extractor = SafetyCheckExtractor()
    tables = [
        [
            ["부서명", "성명(성별)", "", "연령", "직급", "발생시간", "상해종류", "재해경위", ""],
            [
                "물류1과",
                "서정호(남)",
                "",
                "",
                "우정실무원",
                "9. 9.(수) 18:50",
                "찰과상",
                "서단 주차장 연석에 걸려 넘어짐(우측 팔 꿈치 및 좌측 검지 찰과상)",
                "",
            ],
            ["- 조치사항 :응급조치 후 작업장 복귀 * 수시위험성평가, 재발방지대책 수립, 산업재해조사표 제출(1개월 이내) 포함하여 조치사항 기재"],
        ]
    ]
    mixed_text = (
        "【붙임6】관리감독자 안전보건 점검 일지 ※ 재해현황\n"
        "전 주 집 익산,김제 ’20.9월 190.6 2.7 621,074 182.6 2.3 424,253 8.0 0.4 196,821 3대 "
        "물류1과 서정호(남) 우정실무원 찰과상\n"
        "18:50 꿈치 및 좌측 검지 찰과상)\n"
        "청 주 집 세종 외 3국 ’20.1월 345.0 6.2 1,005,014 184.9 4.4 640,922 39.5 1.8 364,092 5대\n"
    )
    _, incidents = extractor.extract(_document(mixed_text, tables), date(2026, 9, 9))
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident.department == "물류1과"
    assert incident.victim_name == "서정호"
    assert incident.gender == "남"
    assert incident.occurrence_time == "18:50"
    assert incident.injury_type == "찰과상"
    assert "서단 주차장" in (incident.description or "")
    assert "익산" not in (incident.description or "")
    assert "621,074" not in (incident.description or "")
    assert "응급조치 후 작업장 복귀" in (incident.description or "")


def test_text_fallback_does_not_treat_abrasion_as_department():
    extractor = SafetyCheckExtractor()
    text = (
        "관리감독자 안전보건 점검 일지\n"
        "※ 재해현황\n"
        "부서명 성명(성별) 연령 직급 발생시간 상해종류 재해경위\n"
        "물류1과 최현국(남) 우정실무원 20:20 찰과상 롤파렛 사이에 손가락 끼임\n"
        "* 수시위험성평가\n"
    )
    _, incidents = extractor.extract(_document(text), date(2026, 9, 7))
    assert len(incidents) == 1
    assert incidents[0].department == "물류1과"
    assert incidents[0].injury_type == "찰과상"
    assert incidents[0].victim_name == "최현국"

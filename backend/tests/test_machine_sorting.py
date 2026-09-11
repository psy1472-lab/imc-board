from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.entities import MachineSortingLine
from infrastructure.pdf.extractors.operations import MachineSortingExtractor
from infrastructure.pdf.reader import PdfDocument, PdfPage


MACHINE_SORTING_TABLE = [
    ["구 분", None, "처리물량(단위:개)", None, None, None, "비 고"],
    [None, None, "기계구분", "점유비", "①수작업", "계", None],
    ["발\n송", "1단", "86,168", "25.8", "44,891", "379,465", "② 수작업 투입인력(M*H) : 202"],
    [None, "2단", "95,751", "28.6", None, None, None],
    [None, "3단", "152,656", "45.6", None, None, None],
    ["도\n착", "1단", "35,503", "26.5", "8,487", "142,464", "② 수작업 투입인력(M*H) : 26"],
    [None, "2단", "36,811", "27.5", None, None, None],
    [None, "3단", "61,664", "46.0", None, None, None],
    ["합 계", None, "468,553", None, "53,378", "521,929", "수작업 총 합계(①+③+④) : 53,600"],
]

MACHINE_SORTING_TEXT = """
 기계구분/수작업 처리물량 현황
처리물량(단위:개)
구 분 비 고
기계구분 점유비 ①수작업 계
1단 86,168 25.8
발 ② 수작업 투입인력(M*H) : 202
2단 95,751 28.6 44,891 379,465
송 ※ 인시당 처리물량(①/②)(개) : 222
3단 152,656 45.6
1단 35,503 26.5
도 ② 수작업 투입인력(M*H) : 26
2단 36,811 27.5 8,487 142,464
착 ※ 인시당 처리물량(①/②)(개) : 326
3단 61,664 46.0
합 계 468,553 53,378 521,929 수작업 총 합계(①+③+④) : 53,600
 소포위탁배달원 개인별 분류 및 집배원 팀별 구분
"""


def _by_key(lines: list[MachineSortingLine]) -> dict[tuple[str, int], MachineSortingLine]:
    return {(item.stream, item.deck): item for item in lines}


def test_machine_sorting_from_table():
    document = PdfDocument(
        path="machine.pdf",
        pages=[
            PdfPage(
                index=0,
                text="기계구분/수작업 처리물량 현황",
                tables=[MACHINE_SORTING_TABLE],
            )
        ],
    )
    lines = MachineSortingExtractor().extract(document, date(2026, 9, 8))
    keyed = _by_key(lines)
    assert len(keyed) == 6
    assert keyed[("dispatch", 1)].volume == 86168
    assert keyed[("dispatch", 1)].share_rate == 25.8
    assert keyed[("dispatch", 2)].volume == 95751
    assert keyed[("dispatch", 3)].volume == 152656
    assert keyed[("dispatch", 3)].share_rate == 45.6
    assert keyed[("arrival", 1)].volume == 35503
    assert keyed[("arrival", 1)].share_rate == 26.5
    assert keyed[("arrival", 2)].volume == 36811
    assert keyed[("arrival", 3)].volume == 61664
    assert keyed[("arrival", 3)].share_rate == 46.0


def test_machine_sorting_text_fallback():
    document = PdfDocument(
        path="machine.pdf",
        pages=[PdfPage(index=0, text=MACHINE_SORTING_TEXT, tables=[])],
    )
    lines = MachineSortingExtractor().extract(document, date(2026, 9, 8))
    keyed = _by_key(lines)
    assert keyed[("dispatch", 1)].volume == 86168
    assert keyed[("dispatch", 2)].share_rate == 28.6
    assert keyed[("arrival", 3)].volume == 61664
    assert keyed[("arrival", 3)].share_rate == 46.0


def test_machine_sorting_trend_serialization():
    from infrastructure.db.sqlite_repository import SqliteRepository

    repo = SqliteRepository.__new__(SqliteRepository)
    grouped = {
        "2026-09-07": {
            "dispatch": {
                1: {"volume": 100, "shareRate": 20.0},
                2: {"volume": 200, "shareRate": 30.0},
                3: {"volume": 300, "shareRate": 50.0},
            },
            "arrival": {},
        },
        "2026-09-08": {
            "dispatch": {
                1: {"volume": 110, "shareRate": 21.0},
                2: {"volume": 210, "shareRate": 31.0},
                3: {"volume": 310, "shareRate": 48.0},
            },
            "arrival": {1: {"volume": 50, "shareRate": 25.0}},
        },
    }
    series = repo._serialize_machine_sorting_trend(grouped, ["2026-09-07", "2026-09-08"])
    assert series["dates"] == ["09-07", "09-08"]
    assert series["dispatch"]["deck1Volume"] == [100, 110]
    assert series["dispatch"]["deck3Share"] == [50.0, 48.0]
    assert series["arrival"]["deck1Volume"] == [None, 50]

    weekday = repo._serialize_machine_sorting_weekday(grouped, ["2026-09-07", "2026-09-08"])
    assert weekday["mode"] == "weekday"
    assert weekday["dispatch"]["deck1Volume"][0] == 100
    assert weekday["dispatch"]["deck1Volume"][1] == 110
    assert weekday["arrival"]["deck1Share"][1] == 25.0

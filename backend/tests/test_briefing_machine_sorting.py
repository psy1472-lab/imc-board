import unittest
from unittest.mock import MagicMock

from application.briefing_service import BriefingService


class BriefingMachineSortingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = BriefingService(MagicMock())

    def test_deck_items_include_dispatch_arrival_and_compare(self) -> None:
        equipment = {
            "meta": {"reportDate": "2026-09-01"},
            "summary": {
                "ipsRate": 98.0,
                "ipsTarget": 97.0,
                "sortingRate": 97.5,
                "rejectRate": 2.0,
                "unreadRate": 1.0,
                "shortcutRate": 3.0,
            },
            "benchmarks": {
                "prevDay": {
                    "ipsRate": 98.0,
                    "sortingRate": 97.5,
                    "rejectRate": 2.0,
                    "unreadRate": 1.0,
                    "shortcutRate": 3.0,
                },
                "avg7d": {
                    "ipsRate": 98.0,
                    "sortingRate": 97.5,
                    "rejectRate": 2.0,
                    "unreadRate": 1.0,
                    "shortcutRate": 3.0,
                },
                "sameWeekday": {
                    "ipsRate": 98.0,
                    "sortingRate": 97.5,
                    "rejectRate": 2.0,
                    "unreadRate": 1.0,
                    "shortcutRate": 3.0,
                },
            },
            "machineSorting": {
                "dispatch": [
                    {"deck": 1, "volume": 100, "shareRate": 50.0},
                    {"deck": 2, "volume": 60, "shareRate": 30.0},
                    {"deck": 3, "volume": 40, "shareRate": 20.0},
                ],
                "arrival": [
                    {"deck": 1, "volume": 80, "shareRate": 40.0},
                    {"deck": 2, "volume": 80, "shareRate": 40.0},
                    {"deck": 3, "volume": 40, "shareRate": 20.0},
                ],
            },
            "machineSortingTrends": {
                "30d": {
                    "reportDates": ["2026-08-25", "2026-09-01"],
                    "dispatch": {
                        "deck1Share": [40.0, 50.0],
                        "deck2Share": [35.0, 30.0],
                        "deck3Share": [25.0, 20.0],
                    },
                    "arrival": {
                        "deck1Share": [41.0, 40.0],
                        "deck2Share": [39.0, 40.0],
                        "deck3Share": [20.0, 20.0],
                    },
                }
            },
        }

        section = self.service._build_equipment_section(equipment, [])
        labels = [item["label"] for item in section["items"]]
        self.assertEqual(
            labels[:5],
            ["IPS", "구분율", "기계구분 1단", "기계구분 2단", "기계구분 3단"],
        )

        deck1 = section["items"][2]
        self.assertEqual(deck1["value"], 50.0)
        self.assertEqual(deck1["unit"], "%")
        self.assertIn("발송 50.0%", deck1["text"])
        self.assertIn("도착 40.0%", deck1["text"])
        self.assertIn("발송 전일 대비", deck1["text"])
        self.assertNotIn("기계구분 단별 점유비 데이터 없음", section["gaps"])

    def test_missing_machine_sorting_adds_gap(self) -> None:
        equipment = {
            "meta": {"reportDate": "2026-09-01"},
            "summary": {"ipsRate": None, "ipsTarget": 97.0},
            "benchmarks": {},
            "machineSorting": {"dispatch": [], "arrival": []},
        }
        section = self.service._build_equipment_section(equipment, [])
        labels = [item["label"] for item in section["items"]]
        self.assertNotIn("기계구분 1단", labels)
        self.assertIn("기계구분 단별 점유비 데이터 없음", section["gaps"])


if __name__ == "__main__":
    unittest.main()

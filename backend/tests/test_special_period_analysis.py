import unittest
from datetime import date

from domain.operation_period import (
    SPECIAL_PERIOD_NONE_REGISTERED_MESSAGE,
    SPECIAL_PERIOD_PRIOR_MISSING_MESSAGE,
    build_special_period_analysis,
    comparison_offsets,
    expand_period_window,
    match_prior_year_period,
    period_length_days,
    quota_compliance_rate,
    select_special_period,
    subtract_one_year,
    yoy_change_percent,
)


def period(period_id: int, start: str, end: str, period_type: str = "special_communication") -> dict:
    return {
        "id": period_id,
        "periodType": period_type,
        "startDate": start,
        "endDate": end,
        "note": None,
    }


class SpecialPeriodMatchingTests(unittest.TestCase):
    def test_expand_period_window_adds_seven_days_each_side(self):
        window = expand_period_window(period(1, "2026-02-10", "2026-02-12"))
        self.assertEqual(window, (date(2026, 2, 3), date(2026, 2, 19)))

    def test_period_length_is_inclusive(self):
        self.assertEqual(period_length_days(period(1, "2026-02-10", "2026-02-12")), 3)

    def test_leap_day_subtract_one_year(self):
        self.assertEqual(subtract_one_year(date(2024, 2, 29)), date(2023, 2, 28))

    def test_match_prior_year_picks_closest_start(self):
        current = period(10, "2026-02-10", "2026-02-20")
        periods = [
            current,
            period(1, "2025-01-28", "2025-02-08"),
            period(2, "2025-02-12", "2025-02-22"),
            period(3, "2025-09-05", "2025-09-15"),
            period(4, "2025-06-20", "2025-06-22", "post_shopping_discount"),
        ]
        matched = match_prior_year_period(current, periods)
        self.assertEqual(matched["id"], 2)

    def test_match_prior_year_ignores_later_and_other_types(self):
        current = period(10, "2026-02-10", "2026-02-20")
        periods = [
            current,
            period(8, "2026-09-15", "2026-09-25"),
            period(4, "2025-02-11", "2025-02-18", "post_shopping_discount"),
        ]
        self.assertIsNone(match_prior_year_period(current, periods))

    def test_select_period_prefers_covering_reference_date(self):
        periods = [
            period(1, "2026-02-10", "2026-02-20"),
            period(2, "2026-09-15", "2026-09-25"),
        ]
        selected = select_special_period(periods, reference_date=date(2026, 9, 18))
        self.assertEqual(selected["id"], 2)

    def test_select_period_falls_back_to_latest(self):
        periods = [
            period(1, "2025-02-10", "2025-02-20"),
            period(2, "2026-02-10", "2026-02-20"),
        ]
        selected = select_special_period(periods, reference_date=date(2026, 3, 1))
        self.assertEqual(selected["id"], 2)


class SpecialPeriodAlignmentTests(unittest.TestCase):
    def test_offsets_follow_the_longer_period(self):
        offsets = comparison_offsets(3, 5)
        self.assertEqual(offsets[0], -7)
        self.assertEqual(offsets[-1], 11)
        self.assertIn(0, offsets)

    def test_length_mismatch_pads_missing_days_with_null(self):
        current = period(2, "2026-02-10", "2026-02-12")
        prior = period(1, "2025-02-10", "2025-02-14")
        daily = {
            "2026-02-10": {"totalVolume": 100.0},
            "2026-02-11": {"totalVolume": 110.0},
            "2026-02-12": {"totalVolume": 120.0},
            "2025-02-10": {"totalVolume": 90.0},
            "2025-02-14": {"totalVolume": 95.0},
        }
        payload = build_special_period_analysis(
            [current, prior],
            daily,
            period_id=2,
        )
        by_offset = {point["offset"]: point for point in payload["series"]}
        self.assertIsNone(by_offset[3]["volume"]["totalCurrent"])
        self.assertEqual(by_offset[4]["volume"]["totalPrior"], 95.0)
        self.assertIsNone(by_offset[1]["volume"]["totalPrior"])
        self.assertEqual(by_offset[0]["volume"]["totalCurrent"], 100.0)

    def test_missing_report_stays_null_not_zero(self):
        current = period(2, "2026-02-10", "2026-02-12")
        prior = period(1, "2025-02-11", "2025-02-13")
        daily = {
            "2026-02-10": {"totalVolume": 100.0, "quotaActual": 10, "quotaStandard": 10, "quotaCompliance": 100.0},
            "2026-02-12": {"totalVolume": 0.0},
        }
        payload = build_special_period_analysis([current, prior], daily, period_id=2)
        by_offset = {point["offset"]: point for point in payload["series"]}
        self.assertIsNone(by_offset[1]["volume"]["totalCurrent"])
        self.assertIsNone(by_offset[1]["quota"]["actualCurrent"])
        self.assertEqual(by_offset[2]["volume"]["totalCurrent"], 0.0)
        self.assertIsNone(by_offset[0]["volume"]["totalPrior"])

    def test_prior_year_missing_leaves_series_empty_and_shows_message(self):
        current = period(1, "2026-02-10", "2026-02-12")
        payload = build_special_period_analysis(
            [current],
            {"2026-02-10": {"totalVolume": 100.0}},
            period_id=1,
        )
        self.assertTrue(payload["priorMissing"])
        self.assertEqual(payload["message"], SPECIAL_PERIOD_PRIOR_MISSING_MESSAGE)
        self.assertIsNone(payload["priorPeriod"])
        self.assertTrue(all(point["volume"]["totalPrior"] is None for point in payload["series"]))
        self.assertIsNone(payload["kpi"]["totalVolume"]["prior"])
        self.assertIsNone(payload["kpi"]["totalVolume"]["changePercent"])

    def test_no_registered_period_returns_guidance(self):
        payload = build_special_period_analysis([], {}, reference_date=date(2026, 2, 10))
        self.assertEqual(payload["message"], SPECIAL_PERIOD_NONE_REGISTERED_MESSAGE)
        self.assertEqual(payload["series"], [])
        self.assertIsNone(payload["kpi"])

    def test_window_sum_and_average_skip_nulls(self):
        current = period(2, "2026-02-10", "2026-02-11")
        prior = period(1, "2025-02-11", "2025-02-12")
        daily = {
            "2026-02-10": {
                "totalVolume": 100.0,
                "quotaActual": 12,
                "quotaStandard": 10,
                "quotaCompliance": quota_compliance_rate(12, 10),
            },
            "2026-02-11": {
                "totalVolume": 50.0,
                "quotaActual": 8,
                "quotaStandard": 10,
                "quotaCompliance": quota_compliance_rate(8, 10),
            },
            "2025-02-11": {
                "totalVolume": 80.0,
                "quotaActual": 10,
                "quotaStandard": 10,
                "quotaCompliance": 100.0,
            },
        }
        payload = build_special_period_analysis([current, prior], daily, period_id=2)
        self.assertEqual(payload["kpi"]["totalVolume"]["current"], 150.0)
        self.assertEqual(payload["kpi"]["totalVolume"]["prior"], 80.0)
        self.assertEqual(payload["kpi"]["totalVolume"]["changePercent"], 87.5)
        self.assertEqual(payload["kpi"]["quotaActual"]["current"], 20)
        self.assertEqual(payload["kpi"]["quotaComplianceRate"]["current"], 100.0)

    def test_quota_compliance_rate(self):
        self.assertEqual(quota_compliance_rate(12, 10), 120.0)
        self.assertIsNone(quota_compliance_rate(10, 0))
        self.assertIsNone(quota_compliance_rate(None, 10))
        self.assertEqual(yoy_change_percent(150.0, 80.0), 87.5)


if __name__ == "__main__":
    unittest.main()

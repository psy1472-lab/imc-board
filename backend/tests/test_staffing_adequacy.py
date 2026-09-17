import unittest

from domain.staffing_adequacy import (
    build_tomorrow_staffing_items,
    compute_night_shift_metrics,
    diagnose_remaining_volume,
    estimate_staffing_adequacy,
    filter_zero_remaining_reference_days,
)


def _reference_day(
    total_volume_k: float,
    *,
    remaining_volume_k: float = 0.0,
    night_avg_staff: float,
    night_peak_staff: int,
    night_avg_productivity: float = 180.0,
) -> dict:
    return {
        "totalVolumeK": total_volume_k,
        "remainingVolumeK": remaining_volume_k,
        "nightAvgStaff": night_avg_staff,
        "nightPeakStaff": night_peak_staff,
        "nightAvgProductivity": night_avg_productivity,
    }


class StaffingAdequacyTests(unittest.TestCase):
    def test_compute_night_shift_metrics(self):
        hourly = {
            "slots": ["~18", "18", "19", "20", "21", "22", "23", "00", "01", "02", "03", "04", "05", "06"],
            "staff": [None, 166, 212, 298, 301, 215, 208, 276, 293, 250, 220, 200, 180, None],
            "productivity": [None, 216, 195, 140, 146, 164, 213, 122, 158, 170, 180, 190, 200, None],
            "volume": [None, 36, 41, 42, 44, 35, 44, 34, 47, 30, 20, 10, 5, None],
        }
        metrics = compute_night_shift_metrics(hourly)
        self.assertEqual(metrics.avg_staff, 234.9)
        self.assertEqual(metrics.peak_staff, 301)
        self.assertEqual(metrics.total_volume_k, 388.0)

    def test_filter_zero_remaining_reference_days_prefers_similar_volume(self):
        days = [
            _reference_day(461, night_avg_staff=176, night_peak_staff=237),
            _reference_day(481, night_avg_staff=201, night_peak_staff=259),
            _reference_day(513, night_avg_staff=189, night_peak_staff=253),
            _reference_day(350, night_avg_staff=150, night_peak_staff=200),
            _reference_day(500, remaining_volume_k=20, night_avg_staff=230, night_peak_staff=300),
        ]
        filtered = filter_zero_remaining_reference_days(days, 484.0)
        self.assertTrue(all(day["remainingVolumeK"] == 0 for day in filtered))
        self.assertGreaterEqual(len(filtered), 3)

    def test_estimate_staffing_adequacy_scales_with_volume(self):
        days = [
            _reference_day(461, night_avg_staff=176, night_peak_staff=237),
            _reference_day(481, night_avg_staff=201, night_peak_staff=259),
            _reference_day(513, night_avg_staff=189, night_peak_staff=253),
            _reference_day(548, night_avg_staff=210, night_peak_staff=290),
        ]
        estimate = estimate_staffing_adequacy(500.0, days)
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertGreater(estimate.night_avg_staff, 190)
        self.assertGreater(estimate.night_peak_staff or 0, 250)
        self.assertEqual(estimate.reference_sample_count, 4)

    def test_diagnose_remaining_volume_flags_productivity_drop(self):
        days = [
            _reference_day(461, night_avg_staff=176, night_peak_staff=237, night_avg_productivity=185),
            _reference_day(481, night_avg_staff=201, night_peak_staff=259, night_avg_productivity=182),
            _reference_day(513, night_avg_staff=189, night_peak_staff=253, night_avg_productivity=180),
        ]
        night_metrics = compute_night_shift_metrics(
            {
                "slots": ["18", "19", "20", "21", "22", "23", "00", "01", "02", "03", "04", "05"],
                "staff": [280, 290, 300, 310, 280, 260, 250, 240, 230, 220, 210, 200],
                "productivity": [110, 105, 108, 109, 112, 115, 110, 108, 107, 110, 112, 115],
                "volume": [30, 35, 40, 42, 38, 36, 34, 40, 35, 30, 20, 10],
            }
        )
        text = diagnose_remaining_volume(431.0, 21.0, night_metrics, days)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("생산성", text)

    def test_build_tomorrow_staffing_items_returns_three_blocks(self):
        days = [
            _reference_day(461, night_avg_staff=176, night_peak_staff=237),
            _reference_day(481, night_avg_staff=201, night_peak_staff=259),
            _reference_day(513, night_avg_staff=189, night_peak_staff=253),
        ]
        items = build_tomorrow_staffing_items(355.0, days, None)
        labels = [item["label"] for item in items]
        self.assertEqual(
            labels,
            ["야간 적정인력(평균)", "야간 적정인력(피크)", "잔량 0 목표 인력"],
        )


if __name__ == "__main__":
    unittest.main()

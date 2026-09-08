import unittest
from datetime import date

from domain.volume_forecast import (
    VolumeForecastResult,
    build_volume_forecast_text,
    estimate_staff_for_volume,
    forecast_national_volume,
    forecast_next_day_volume,
    resolve_forecast_target_date,
)


class VolumeForecastTests(unittest.TestCase):
    def test_friday_forecast_targets_sunday(self):
        friday = date(2026, 6, 19)
        target = resolve_forecast_target_date(friday)
        self.assertEqual(target.weekday(), 6)
        self.assertEqual(target.isoformat(), "2026-06-21")

        result = forecast_next_day_volume(
            "2026-06-19",
            today_volume=500.0,
            avg_7d_volume=350.0,
            avg_30d_volume=340.0,
            recent_7d_volumes=[480.0, 490.0, 500.0],
            weekday_volumes=[510.0, 530.0, 520.0, 515.0, 505.0, 45.0, 480.0],
            weekday_sample_counts=[4, 4, 4, 4, 4, 4, 4],
            tomorrow_day_type="sunday",
            forecast_target_date="2026-06-21",
            forecast_target_note="토요일 제외, 일요일 기준",
            same_type_baseline=470.0,
            same_type_avg_7d=465.0,
            same_type_avg_30d=460.0,
            same_type_recent_volumes=[455.0, 462.0, 468.0, 470.0],
            same_type_sample_count=4,
            today_type_avg_7d=495.0,
            seasonal_naive_1w=468.0,
            seasonal_naive_4w=465.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tomorrow_weekday_label, "일")
        self.assertEqual(result.tomorrow_day_type, "sunday")
        self.assertEqual(result.forecast_target_note, "토요일 제외, 일요일 기준")
        self.assertAlmostEqual(result.forecast_volume, 466.0, delta=10.0)

    def test_forecast_blends_weekday_recent_and_trend(self):
        result = forecast_next_day_volume(
            "2026-06-22",
            today_volume=520.0,
            avg_7d_volume=500.0,
            avg_30d_volume=510.0,
            recent_7d_volumes=[470.0, 480.0, 490.0, 500.0, 510.0, 515.0, 520.0],
            weekday_volumes=[510.0, 530.0, 520.0, 515.0, 505.0, 480.0, 470.0],
            weekday_sample_counts=[4, 4, 4, 4, 4, 2, 2],
            seasonal_naive_1w=525.0,
            seasonal_naive_4w=522.0,
            same_type_baseline=530.0,
            same_type_sample_count=4,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tomorrow_weekday_label, "화")
        self.assertEqual(result.tomorrow_day_type, "weekday")
        self.assertEqual(result.seasonal_naive_1w, 525.0)
        self.assertEqual(result.forecast_method, "seasonal_naive_weekday")

    def test_forecast_uses_recent_average_when_weekday_missing(self):
        result = forecast_next_day_volume(
            "2026-06-22",
            today_volume=None,
            avg_7d_volume=488.5,
            avg_30d_volume=490.0,
            recent_7d_volumes=[480.0, 485.0, 488.0, 490.0, 492.0, 495.0, 498.0],
            weekday_volumes=[None, None, None, None, None, None, None],
            weekday_sample_counts=[0, 0, 0, 0, 0, 0, 0],
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result.forecast_volume, 488.0)

    def test_seasonal_naive_beats_mixed_average_for_weekday(self):
        mixed = forecast_next_day_volume(
            "2026-06-22",
            today_volume=520.0,
            avg_7d_volume=350.0,
            avg_30d_volume=340.0,
            recent_7d_volumes=[500.0, 480.0, 45.0, 500.0, 490.0, 480.0, 520.0],
            weekday_volumes=[510.0, 530.0, 520.0, 515.0, 505.0, 45.0, 42.0],
            weekday_sample_counts=[4, 4, 4, 4, 4, 4, 4],
        )
        seasonal = forecast_next_day_volume(
            "2026-06-22",
            today_volume=520.0,
            avg_7d_volume=350.0,
            avg_30d_volume=340.0,
            recent_7d_volumes=[500.0, 480.0, 45.0, 500.0, 490.0, 480.0, 520.0],
            weekday_volumes=[510.0, 530.0, 520.0, 515.0, 505.0, 45.0, 42.0],
            weekday_sample_counts=[4, 4, 4, 4, 4, 4, 4],
            tomorrow_day_type="weekday",
            same_type_baseline=530.0,
            same_type_sample_count=4,
            seasonal_naive_1w=528.0,
            seasonal_naive_4w=527.0,
        )

        self.assertIsNotNone(mixed)
        self.assertIsNotNone(seasonal)
        assert mixed is not None and seasonal is not None
        self.assertAlmostEqual(seasonal.forecast_volume, 528.0, delta=5.0)
        self.assertGreater(
            abs(mixed.forecast_volume - 530.0),
            abs(seasonal.forecast_volume - 530.0),
        )

    def test_forecast_returns_none_without_data(self):
        result = forecast_next_day_volume(
            "2026-06-22",
            today_volume=None,
            avg_7d_volume=None,
            avg_30d_volume=None,
            recent_7d_volumes=[],
            weekday_volumes=[None] * 7,
            weekday_sample_counts=[0] * 7,
        )
        self.assertIsNone(result)

    def test_build_volume_forecast_text_includes_seasonal_naive(self):
        text = build_volume_forecast_text(
            VolumeForecastResult(
                tomorrow_date="2026-06-23",
                tomorrow_weekday_label="화",
                tomorrow_day_type="weekday",
                forecast_volume=542.3,
                forecast_national_volume=612.8,
                weekday_average=529.8,
                recent_7d_average=518.2,
                recent_30d_average=512.0,
                recent_3d_average=535.0,
                today_volume=535.0,
                weekday_sample_count=4,
                trend_factor=1.03,
                momentum_factor=1.02,
                recent_trend_direction="상승",
                confidence="high",
                seasonal_naive_1w=528.0,
                seasonal_naive_4w=531.0,
                forecast_method="seasonal_naive_weekday",
            )
        )
        self.assertIn("542.3천개", text)
        self.assertIn("612.8천개", text)
        self.assertIn("전국접수물량", text)
        self.assertIn("화", text)
        self.assertIn("Seasonal Naive", text)
        self.assertIn("4주 평균", text)
        self.assertIn("상승", text)

    def test_forecast_applies_no_parcel_day_adjustment(self):
        result = forecast_next_day_volume(
            "2026-06-22",
            today_volume=520.0,
            avg_7d_volume=500.0,
            avg_30d_volume=510.0,
            recent_7d_volumes=[470.0, 480.0, 490.0, 500.0, 510.0, 515.0, 520.0],
            weekday_volumes=[510.0, 530.0, 520.0, 515.0, 505.0, 480.0, 470.0],
            weekday_sample_counts=[4, 4, 4, 4, 4, 2, 2],
            seasonal_naive_1w=525.0,
            seasonal_naive_4w=522.0,
            same_type_baseline=530.0,
            same_type_sample_count=4,
            operation_periods=[
                {
                    "periodType": "no_parcel_day",
                    "startDate": "2026-06-23",
                    "endDate": "2026-06-23",
                }
            ],
            historical_no_parcel_avg=15.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertLess(result.forecast_volume, 400.0)
        self.assertGreater(result.forecast_volume, 15.0)
        self.assertEqual(result.operation_period_labels, ("위탁배달원 하계 휴식기간",))

    def test_estimate_staff_for_volume(self):
        staff = estimate_staff_for_volume(550.0, 500.0, 170.0)
        self.assertEqual(staff, 187.0)

    def test_forecast_national_volume_uses_seasonal_baseline(self):
        forecast = forecast_national_volume(
            target_day_type="weekday",
            seasonal_naive_1w=600.0,
            seasonal_naive_4w=590.0,
            same_type_baseline=585.0,
            same_type_avg_7d=580.0,
            today_volume=610.0,
            today_type_avg_7d=600.0,
        )
        self.assertIsNotNone(forecast)
        assert forecast is not None
        self.assertGreater(forecast, 580.0)


if __name__ == "__main__":
    unittest.main()

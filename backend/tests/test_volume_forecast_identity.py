import unittest
from datetime import date, timedelta

from domain.volume_forecast import (
    apply_identity_volume_forecast,
    build_forecast_accuracy_text,
    forecast_next_day_volume,
    summarize_forecast_accuracy,
)
from domain.volume_forecast_identity import (
    compare_identity_forecasts,
    compose_volume_from_national_and_rate,
    forecast_processing_rate,
    impute_national_features,
    processing_rate,
    reconcile_volume_identity,
    walk_forward_identity_points,
    IdentityForecastPoint,
)


class VolumeForecastIdentityTests(unittest.TestCase):
    def test_compose_volume_from_national_and_rate(self):
        self.assertEqual(compose_volume_from_national_and_rate(2000.0, 27.0), 540.0)
        self.assertIsNone(compose_volume_from_national_and_rate(None, 27.0))
        self.assertIsNone(compose_volume_from_national_and_rate(2000.0, None))

    def test_processing_rate_missing_national_is_none(self):
        self.assertIsNone(processing_rate(540.0, None))
        self.assertIsNone(processing_rate(540.0, 0))
        self.assertEqual(processing_rate(540.0, 2000.0), 27.0)

    def test_forecast_processing_rate_uses_same_weekday_then_median(self):
        history = [
            (date(2026, 6, 1), 26.0),
            (date(2026, 6, 2), 27.0),
            (date(2026, 6, 8), 26.5),
            (date(2026, 6, 9), 27.5),
            (date(2026, 6, 15), 26.2),
            (date(2026, 6, 16), 27.4),
        ]
        tuesday = forecast_processing_rate(date(2026, 6, 23), history)
        self.assertAlmostEqual(tuesday, (27.0 + 27.5 + 27.4) / 3, places=2)

        sparse = [(date(2026, 6, 2), 30.0), (date(2026, 6, 3), 20.0)]
        fallback = forecast_processing_rate(date(2026, 6, 23), sparse)
        self.assertEqual(fallback, 25.0)

        self.assertIsNone(forecast_processing_rate(date(2026, 6, 23), []))

    def test_reconcile_prefers_identity_when_direct_rate_drifts(self):
        volume, method = reconcile_volume_identity(
            direct_volume=700.0,
            identity_volume=540.0,
            forecast_national=2000.0,
            weekday_rate=27.0,
        )
        self.assertEqual(volume, 540.0)
        self.assertEqual(method, "identity_reconcile")

        volume, method = reconcile_volume_identity(
            direct_volume=530.0,
            identity_volume=540.0,
            forecast_national=2000.0,
            weekday_rate=27.0,
        )
        self.assertEqual(volume, 540.0)
        self.assertEqual(method, "identity")

        volume, method = reconcile_volume_identity(
            direct_volume=530.0,
            identity_volume=None,
            forecast_national=None,
            weekday_rate=None,
        )
        self.assertEqual(volume, 530.0)
        self.assertEqual(method, "direct")

    def test_reconcile_assist_mode_keeps_direct_unless_drift(self):
        volume, method = reconcile_volume_identity(
            direct_volume=530.0,
            identity_volume=540.0,
            forecast_national=2000.0,
            weekday_rate=27.0,
            prefer_identity=False,
        )
        self.assertEqual(volume, 530.0)
        self.assertEqual(method, "direct")

        volume, method = reconcile_volume_identity(
            direct_volume=700.0,
            identity_volume=540.0,
            forecast_national=2000.0,
            weekday_rate=27.0,
            prefer_identity=False,
        )
        self.assertEqual(volume, 540.0)
        self.assertEqual(method, "identity_reconcile")

    def test_compare_identity_forecasts_prefers_product_when_national_drives_volume(self):
        points = []
        for offset in range(6):
            day = date(2026, 6, 1) + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            national = 1800.0 + offset * 80
            actual = round(national * 0.27, 1)
            points.append(
                IdentityForecastPoint(
                    target_date=day.isoformat(),
                    actual_volume=actual,
                    actual_national=national,
                    actual_rate=27.0,
                    direct_volume=480.0,
                    identity_volume=actual,
                    forecast_national=national,
                    forecast_rate=27.0,
                )
            )
        summary = compare_identity_forecasts(points)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertLess(summary["identityVolumeMape"], summary["directVolumeMape"])
        self.assertTrue(summary["preferIdentity"])
        self.assertEqual(summary["rateMape"], 0.0)

    def test_walk_forward_identity_points_on_synthetic_weekday_series(self):
        observations: list[tuple[str, float, float | None]] = []
        start = date(2026, 3, 2)
        for offset in range(40):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            national = 1900.0 + (offset // 7) * 40
            observations.append((day.isoformat(), round(national * 0.27, 1), national))
        points = walk_forward_identity_points(observations)
        summary = compare_identity_forecasts(points)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertGreaterEqual(summary["sampleCount"], 3)
        self.assertIsNotNone(summary["directVolumeMape"])
        self.assertIsNotNone(summary["identityVolumeMape"])

    def test_impute_national_features_skips_zero_for_compact_gap(self):
        national, ratio = impute_national_features(
            None,
            prev_day_volume=40.0,
            last_weekday_national=2000.0,
            last_weekday_rate=27.0,
        )
        self.assertEqual(national, 2000.0)
        self.assertAlmostEqual(ratio, 100.0 / 27.0, places=4)

        missing, missing_ratio = impute_national_features(None, prev_day_volume=40.0)
        self.assertEqual(missing, 0.0)
        self.assertEqual(missing_ratio, 0.0)

        present, present_ratio = impute_national_features(
            1991.0,
            prev_day_volume=537.0,
        )
        self.assertEqual(present, 1991.0)
        self.assertAlmostEqual(present_ratio, 1991.0 / 537.0, places=4)

    def test_rule_forecast_uses_national_times_rate_when_history_exists(self):
        volume_by_date = {}
        national_by_date = {}
        for weeks in range(1, 6):
            tuesday = date(2026, 6, 23) - timedelta(weeks=weeks)
            volume_by_date[tuesday.isoformat()] = 540.0
            national_by_date[tuesday.isoformat()] = 2000.0
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
            national_seasonal_naive_1w=2000.0,
            national_seasonal_naive_4w=2000.0,
            same_type_national_baseline=2000.0,
            volume_by_date=volume_by_date,
            national_volume_by_date=national_by_date,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.forecast_processing_rate, 27.0, places=1)
        self.assertAlmostEqual(result.forecast_volume, 540.0, delta=15.0)
        self.assertIn("identity", result.forecast_method)

    def test_apply_identity_falls_back_without_national(self):
        volume, rate, method = apply_identity_volume_forecast(
            target_day=date(2026, 6, 23),
            direct_volume=528.0,
            forecast_national=None,
            volume_by_date={"2026-06-16": 520.0},
            national_volume_by_date={},
        )
        self.assertEqual(volume, 528.0)
        self.assertIsNone(rate)
        self.assertEqual(method, "direct")

    def test_apply_identity_ml_residual_keeps_damped_direct(self):
        volume_by_date = {}
        national_by_date = {}
        for weeks in range(1, 5):
            tuesday = date(2026, 6, 23) - timedelta(weeks=weeks)
            volume_by_date[tuesday.isoformat()] = 540.0
            national_by_date[tuesday.isoformat()] = 2000.0
        volume, rate, method = apply_identity_volume_forecast(
            target_day=date(2026, 6, 23),
            direct_volume=600.0,
            forecast_national=2000.0,
            volume_by_date=volume_by_date,
            national_volume_by_date=national_by_date,
            residual_weight=0.3,
        )
        self.assertEqual(method, "identity_ml_residual")
        self.assertAlmostEqual(rate, 27.0, places=1)
        self.assertAlmostEqual(volume, 540.0 + 0.3 * (600.0 - 540.0), delta=1.0)

    def test_accuracy_text_includes_three_factors(self):
        text = build_forecast_accuracy_text(
            540.0,
            537.0,
            forecast_date="2026-09-14",
            forecast_national_volume=2000.0,
            actual_national_volume=1991.0,
            forecast_processing_rate=27.0,
            actual_processing_rate=26.97,
        )
        self.assertIn("처리물량", text)
        self.assertIn("전국접수물량", text)
        self.assertIn("전국대비처리율", text)

    def test_summarize_forecast_accuracy_includes_rate_mape(self):
        rows = [
            {
                "targetDate": "2026-06-22",
                "forecastVolume": 500.0,
                "actualVolume": 510.0,
                "forecastNationalVolume": 1900.0,
                "actualNationalVolume": 2000.0,
                "forecastProcessingRate": 26.0,
                "actualProcessingRate": 27.0,
            },
            {
                "targetDate": "2026-06-23",
                "forecastVolume": 520.0,
                "actualVolume": 500.0,
                "forecastNationalVolume": 2000.0,
                "actualNationalVolume": 1980.0,
                "forecastProcessingRate": 27.0,
                "actualProcessingRate": 26.5,
            },
            {
                "targetDate": "2026-06-24",
                "forecastVolume": 510.0,
                "actualVolume": 515.0,
                "forecastNationalVolume": 2010.0,
                "actualNationalVolume": 1990.0,
                "forecastProcessingRate": 26.5,
                "actualProcessingRate": 26.8,
            },
        ]
        summary = summarize_forecast_accuracy(rows)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertIsNotNone(summary["rateMape"])
        self.assertEqual(summary["rateSampleCount"], 3)


if __name__ == "__main__":
    unittest.main()

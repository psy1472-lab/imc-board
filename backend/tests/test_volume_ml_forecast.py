import unittest
from datetime import date, timedelta

from domain.day_type import resolve_day_type
from domain.volume_forecast import resolve_forecast_target_date
from domain.volume_ml_forecast import (
    FEATURE_NAMES,
    MIN_TRAINING_SAMPLES,
    VolumeMlRow,
    blend_with_seasonal_naive,
    build_feature_vector,
    build_training_dataset,
    infer_special_communication,
    predict_next_volume,
)


def _synthetic_rows(start: date, count: int) -> list[VolumeMlRow]:
    rows: list[VolumeMlRow] = []
    for offset in range(count):
        report_day = start + timedelta(days=offset)
        weekday = report_day.weekday()
        base = 500_000 if weekday < 5 else 40_000
        total = base + (offset % 7) * 10_000
        rows.append(
            VolumeMlRow(
                report_date=report_day,
                total_volume=total,
                national_volume=int(total * 1.2),
                remaining_volume=0,
                day_type=resolve_day_type(report_day),
                report_format="standard" if weekday < 5 else "compact",
            )
        )
    return rows


class VolumeMlForecastTests(unittest.TestCase):
    def test_feature_names(self):
        self.assertEqual(len(FEATURE_NAMES), 18)

    def test_blend_with_seasonal_naive(self):
        blended = blend_with_seasonal_naive(500.0, 400.0, ml_weight=0.5)
        self.assertEqual(blended, 450.0)

    def test_infer_special_communication(self):
        self.assertEqual(infer_special_communication(0, "weekday", "standard"), 0)
        self.assertEqual(infer_special_communication(1000, "weekday", "standard"), 1)
        self.assertEqual(infer_special_communication(0, "sunday", "compact"), 1)

    def test_build_feature_vector_shape(self):
        history = [500.0 + i for i in range(10)]
        volume_map = {f"2026-06-{day:02d}": 500.0 + day for day in range(1, 22)}
        vector = build_feature_vector(
            date(2026, 6, 19),
            date(2026, 6, 21),
            history,
            600.0,
            1,
            volume_by_date=volume_map,
            report_dates=[date(2026, 6, day) for day in range(1, 20)],
        )
        self.assertEqual(len(vector), 18)
        self.assertEqual(vector[0], 6.0)
        self.assertEqual(vector[1], 6.0)

    def test_training_dataset_requires_minimum_history(self):
        rows = _synthetic_rows(date(2026, 1, 1), 10)
        X, y, _, _ = build_training_dataset(rows)
        self.assertLess(len(y), MIN_TRAINING_SAMPLES)

    def test_predict_next_volume_with_synthetic_data(self):
        rows = _synthetic_rows(date(2025, 1, 1), 120)
        report_date = rows[-1].report_date.isoformat()
        result = predict_next_volume(rows, report_date)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreaterEqual(result.training_samples, MIN_TRAINING_SAMPLES)
        self.assertGreater(result.forecast_volume, 0)
        self.assertIn(
            result.best_model_key,
            {"linear_regression", "random_forest", "gradient_boosting", "lightgbm"},
        )

    def test_friday_target_is_sunday_in_ml_pipeline(self):
        friday = date(2026, 6, 19)
        self.assertEqual(resolve_forecast_target_date(friday).weekday(), 6)

    def test_predict_applies_no_parcel_day_adjustment(self):
        rows = _synthetic_rows(date(2025, 1, 1), 120)
        report_date = rows[-1].report_date.isoformat()
        target_day = resolve_forecast_target_date(date.fromisoformat(report_date))
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": target_day.isoformat(),
                "endDate": target_day.isoformat(),
            }
        ]
        result = predict_next_volume(
            rows,
            report_date,
            operation_periods=periods,
            historical_no_parcel_avg=8.0,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertLess(result.forecast_volume, 500.0)
        self.assertGreater(result.forecast_volume, 8.0)
        self.assertEqual(result.operation_period_labels, ("위탁배달원 하계 휴식기간",))


if __name__ == "__main__":
    unittest.main()

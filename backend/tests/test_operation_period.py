import unittest
from datetime import date

from domain.operation_period import (
    apply_operation_period_volume_adjustment,
    classify_forecast_period_category,
    compute_historical_no_parcel_avg,
    compute_historical_same_weekday_in_period,
    compute_historical_special_period_avg,
    no_parcel_period_features,
)
from domain.volume_ml_forecast import resolve_special_communication_flag


class OperationPeriodTests(unittest.TestCase):
    def test_resolve_special_communication_from_registered_period(self):
        periods = [
            {
                "periodType": "post_shopping_discount",
                "startDate": "2026-06-20",
                "endDate": "2026-06-22",
            }
        ]
        flag = resolve_special_communication_flag(
            0,
            "weekday",
            "standard",
            date(2026, 6, 21),
            periods,
        )
        self.assertEqual(flag, 1)

    def test_no_parcel_day_uses_gradual_blend(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-06-23",
                "endDate": "2026-06-23",
            }
        ]
        adjusted, labels = apply_operation_period_volume_adjustment(
            520.0,
            date(2026, 6, 23),
            periods,
            historical_no_parcel_avg=12.5,
        )
        self.assertEqual(adjusted, 266.2)
        self.assertEqual(labels, ("위탁배달원 하계 휴식기간",))

    def test_no_parcel_first_and_last_day_keep_more_base_forecast(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-08-14",
                "endDate": "2026-08-18",
            }
        ]
        first_day, _ = apply_operation_period_volume_adjustment(
            500.0,
            date(2026, 8, 14),
            periods,
            historical_no_parcel_avg=12.5,
        )
        last_day, _ = apply_operation_period_volume_adjustment(
            500.0,
            date(2026, 8, 18),
            periods,
            historical_no_parcel_avg=12.5,
        )
        self.assertGreater(first_day, 100.0)
        self.assertGreater(last_day, 100.0)

    def test_special_period_blends_with_historical_reference(self):
        periods = [
            {
                "periodType": "special_communication",
                "startDate": "2026-02-10",
                "endDate": "2026-02-12",
            },
            {
                "periodType": "special_communication",
                "startDate": "2025-02-11",
                "endDate": "2025-02-13",
            },
        ]
        volume_by_date = {
            "2025-02-11": 400.0,
            "2025-02-12": 420.0,
            "2025-02-13": 410.0,
        }
        adjusted, labels = apply_operation_period_volume_adjustment(
            500.0,
            date(2026, 2, 10),
            periods,
            volume_by_date=volume_by_date,
            before_date=date(2026, 2, 10),
        )
        self.assertEqual(labels, ("특별소통기간",))
        self.assertLess(adjusted, 500.0)
        self.assertGreater(adjusted, 400.0)

    def test_compute_historical_no_parcel_avg(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-05-01",
                "endDate": "2026-05-01",
            },
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-05-08",
                "endDate": "2026-05-08",
            },
        ]
        volume_by_date = {
            "2026-05-01": 10.0,
            "2026-05-08": 20.0,
        }
        avg = compute_historical_no_parcel_avg(
            periods,
            volume_by_date,
            date(2026, 6, 1),
        )
        self.assertEqual(avg, 15.0)

    def test_compute_historical_same_weekday_in_period(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2025-08-15",
                "endDate": "2025-08-19",
            }
        ]
        volume_by_date = {"2025-08-15": 120.0}
        avg = compute_historical_same_weekday_in_period(
            "no_parcel_day",
            date(2026, 8, 14),
            periods,
            volume_by_date,
            date(2026, 8, 14),
        )
        self.assertEqual(avg, 120.0)

    def test_classify_forecast_period_category(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-08-14",
                "endDate": "2026-08-18",
            }
        ]
        self.assertEqual(
            classify_forecast_period_category(date(2026, 8, 14), periods),
            "no_parcel",
        )

    def test_no_parcel_period_features(self):
        periods = [
            {
                "periodType": "no_parcel_day",
                "startDate": "2026-08-14",
                "endDate": "2026-08-18",
            }
        ]
        day_index, days_until = no_parcel_period_features(date(2026, 8, 14), periods)
        self.assertEqual(day_index, 0.0)
        self.assertEqual(days_until, 1.0)


if __name__ == "__main__":
    unittest.main()

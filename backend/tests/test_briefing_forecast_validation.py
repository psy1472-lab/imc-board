import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock

from application.briefing_service import BriefingService
from application.volume_forecast_service import VolumeForecastService
from domain.day_type import resolve_day_type
from domain.forecast_router import VolumeForecastOutcome


class BriefingForecastValidationTests(unittest.TestCase):
    def test_prior_validation_uses_predict_for_target(self):
        repository = MagicMock()
        repository.get_dashboard_summary.return_value = {
            "meta": {"centerName": "IMC", "communicationStatusLabel": "정상"},
        }
        repository.get_volume_analysis.return_value = {
            "summary": {"totalVolume": 461.0},
            "benchmarks": {"avg7d": {"totalVolume": 450.0}},
            "trends": {"7d": {"totalVolume": []}, "weekday": {"totalVolume": [], "sampleCounts": []}},
        }
        repository.get_staffing_analysis.return_value = {"summary": {}, "benchmarks": {}}
        repository.get_transport_analysis.return_value = {"summary": {}, "offices": []}
        repository.get_equipment_analysis.return_value = {"summary": {}, "benchmarks": {}}
        repository.get_safety_analysis.return_value = {
            "summary": {"overallStatus": "NORMAL", "overallLabel": "정상"},
            "anomalies": [],
        }
        repository.get_hourly_volume_pattern.return_value = {}
        repository.get_volume_forecast_context.return_value = {
            "forecastTargetDate": "2026-09-01",
            "tomorrowDayType": "weekday",
            "seasonalNaive4w": 450.0,
        }

        service = BriefingService(repository)
        service.volume_forecast_service = MagicMock(spec=VolumeForecastService)
        service.volume_forecast_service.predict.return_value = VolumeForecastOutcome(
            report_date="2026-08-31",
            target_date="2026-09-01",
            target_day_type="weekday",
            forecast_volume=356.4,
            method="ml_blend",
            method_label="ML+Seasonal Naive",
        )
        service.volume_forecast_service.ml_service = MagicMock()
        service.volume_forecast_service.ml_service.predict.return_value = None
        service.volume_forecast_service.predict_for_target.return_value = VolumeForecastOutcome(
            report_date="2026-08-30",
            target_date="2026-08-31",
            target_day_type="weekday",
            forecast_volume=489.6,
            method="ml_blend",
            method_label="ML+Seasonal Naive",
        )

        briefing = service.generate("2026-08-31")
        validation_items = [
            item
            for item in briefing["tomorrowOutlook"]["items"]
            if item["label"] == "전일 예측 검증"
        ]
        self.assertEqual(len(validation_items), 1)
        self.assertIn("489.6", validation_items[0]["text"])
        service.volume_forecast_service.predict_for_target.assert_called_once()
        call_args = service.volume_forecast_service.predict_for_target.call_args
        self.assertEqual(call_args.args[0], "2026-08-31")


if __name__ == "__main__":
    unittest.main()

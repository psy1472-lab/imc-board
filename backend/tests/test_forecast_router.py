import unittest
from datetime import date

from domain.forecast_router import (
    resolve_forecast_anchor_for_target,
    resolve_feature_anchor_report,
)
from domain.volume_forecast import resolve_forecast_target_date


class ForecastRouterTests(unittest.TestCase):
    def test_friday_target_sunday_anchor_friday(self):
        sunday = date(2026, 6, 21)
        self.assertEqual(resolve_forecast_target_date(date(2026, 6, 19)), sunday)
        self.assertEqual(resolve_forecast_anchor_for_target(sunday), date(2026, 6, 19))

    def test_monday_target_anchor_sunday(self):
        monday = date(2026, 8, 31)
        self.assertEqual(resolve_forecast_anchor_for_target(monday), date(2026, 8, 30))

    def test_feature_anchor_uses_last_report(self):
        report_dates = ["2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28", "2026-08-31"]
        anchor = resolve_feature_anchor_report(report_dates, date(2026, 8, 30))
        self.assertEqual(anchor, "2026-08-28")


if __name__ == "__main__":
    unittest.main()

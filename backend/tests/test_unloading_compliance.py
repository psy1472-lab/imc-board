import unittest

from domain.unloading_compliance import (
    compute_unloading_compliance,
    delayed_hour_slots,
)


def _row(slot, collection=0, quota=0, exchange=0):
    return {
        "hour_slot": slot,
        "collection_vehicles": collection,
        "quota_vehicles": quota,
        "exchange_vehicles": exchange,
    }


class UnloadingComplianceTests(unittest.TestCase):
    def test_delayed_slots_are_after_deadline(self):
        self.assertEqual(delayed_hour_slots("22"), ["23", "00", "01", "02", "03", "04", "05", "06"])
        self.assertEqual(delayed_hour_slots("23"), ["00", "01", "02", "03", "04", "05", "06"])
        self.assertEqual(delayed_hour_slots("02"), ["03", "04", "05", "06"])

    def test_collection_deadline_22(self):
        rows = [
            _row("~18", collection=40),
            _row("21", collection=10),
            _row("22", collection=50),
            _row("23", collection=5),
            _row("00", collection=5),
        ]
        item = next(item for item in compute_unloading_compliance(rows) if item.column == "collection_vehicles")
        self.assertEqual(item.total, 110)
        self.assertEqual(item.delayed, 10)
        self.assertEqual(item.rate, 90.9)
        self.assertEqual(item.severity, "WARNING")
        self.assertIn("지연 10/110대", item.message)
        self.assertIn("22시 기준", item.message)

    def test_quota_and_exchange_deadlines(self):
        rows = [
            _row("22", quota=10, exchange=1),
            _row("23", quota=20, exchange=2),
            _row("00", quota=5, exchange=3),
            _row("02", quota=1, exchange=10),
            _row("03", quota=0, exchange=4),
        ]
        items = {item.column: item for item in compute_unloading_compliance(rows)}
        self.assertEqual(items["quota_vehicles"].delayed, 6)
        self.assertEqual(items["quota_vehicles"].total, 36)
        self.assertIn("23시 기준", items["quota_vehicles"].message)
        self.assertEqual(items["exchange_vehicles"].delayed, 4)
        self.assertEqual(items["exchange_vehicles"].total, 20)
        self.assertEqual(items["exchange_vehicles"].rate, 80.0)
        self.assertIn("02시 기준", items["exchange_vehicles"].message)

    def test_full_compliance_is_normal(self):
        rows = [_row("18", collection=10, quota=8, exchange=3), _row("21", collection=5, quota=2, exchange=1)]
        items = compute_unloading_compliance(rows)
        self.assertTrue(all(item.severity == "NORMAL" for item in items))
        self.assertTrue(all(item.delayed == 0 for item in items))
        self.assertTrue(all(item.rate == 100.0 for item in items))

    def test_skips_series_without_vehicles(self):
        rows = [_row("18", collection=10)]
        items = compute_unloading_compliance(rows)
        self.assertEqual([item.column for item in items], ["collection_vehicles"])


if __name__ == "__main__":
    unittest.main()

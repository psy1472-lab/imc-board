import unittest

from domain.transport_quota import quota_overage, quota_status


class TransportQuotaTests(unittest.TestCase):
    def test_quota_status_normal_when_equal(self):
        self.assertEqual(quota_status(3, 3), "NORMAL")
        self.assertEqual(quota_overage(3, 3), 0)

    def test_quota_status_warning_only_when_actual_exceeds_standard(self):
        self.assertEqual(quota_status(4, 3), "WARNING")
        self.assertEqual(quota_overage(4, 3), 1)

    def test_quota_status_normal_when_under_quota(self):
        self.assertEqual(quota_status(5, 6), "NORMAL")
        self.assertEqual(quota_overage(5, 6), 0)


if __name__ == "__main__":
    unittest.main()

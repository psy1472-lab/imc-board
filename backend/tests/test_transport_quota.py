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

    def test_arrival_after_23(self):
        from domain.transport_quota import is_arrival_after_23, office_status_label

        self.assertFalse(is_arrival_after_23("22:45"))
        self.assertFalse(is_arrival_after_23("23:00"))
        self.assertTrue(is_arrival_after_23("23:01"))
        self.assertTrue(is_arrival_after_23("00:08", volume=17637, vehicles_actual=9))
        self.assertFalse(is_arrival_after_23("00:00", volume=0, vehicles_actual=0))
        self.assertEqual(office_status_label(overage=True, delayed=False), "초과")
        self.assertEqual(office_status_label(overage=False, delayed=True), "지연")
        self.assertEqual(office_status_label(overage=True, delayed=True), "초과/지연")
        self.assertEqual(office_status_label(overage=False, delayed=False), "정상")


if __name__ == "__main__":
    unittest.main()

import unittest

from interfaces.api.http_cache import build_report_etag, if_none_match_matches


class HttpCacheTests(unittest.TestCase):
    def test_etag_includes_date_compare_and_ingest(self):
        etag = build_report_etag("2025-01-02", "prev_day", "2026-09-08T13:18:52")
        self.assertEqual(etag, 'W/"2025-01-02:prev_day:2026-09-08T13:18:52"')

    def test_if_none_match_accepts_listed_etag(self):
        etag = build_report_etag("2025-01-02", "prev_day", "v1")
        self.assertTrue(if_none_match_matches(etag, etag))
        self.assertTrue(if_none_match_matches(f"W/\"other\", {etag}", etag))
        self.assertFalse(if_none_match_matches('W/"other"', etag))


if __name__ == "__main__":
    unittest.main()

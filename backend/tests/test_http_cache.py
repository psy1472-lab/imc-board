import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.db.sqlite_repository import SqliteRepository
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


class DashboardCacheRevisionTests(unittest.TestCase):
    def test_revision_changes_when_exchange_values_change(self):
        with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = SqliteRepository(str(Path(tmp) / "test.db"))
            with repo._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO report_metadata (report_date, center_name, ingested_at)
                    VALUES (?, ?, ?)
                    """,
                    ("2026-10-14", "중부권IMC", "2026-10-14T23:26:08"),
                )
                conn.execute(
                    """
                    INSERT INTO quota_exchange (
                        report_date, quarter_standard, quarter_actual,
                        exchange_standard, exchange_actual, exchange_remaining
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("2026-10-14", 87, 86, None, None, 0),
                )
                conn.commit()

            before = repo.get_dashboard_cache_revision("2026-10-14")
            with repo._connect() as conn:
                conn.execute(
                    """
                    UPDATE quota_exchange
                    SET exchange_standard = ?, exchange_actual = ?
                    WHERE report_date = ?
                    """,
                    (129, 114, "2026-10-14"),
                )
                conn.commit()
            after = repo.get_dashboard_cache_revision("2026-10-14")

            self.assertNotEqual(before, after)
            self.assertIn("114", after)
            self.assertNotEqual(
                build_report_etag("2026-10-14", f"prev_day:live-prev-kpi:{before}", "2026-10-14T23:26:08"),
                build_report_etag("2026-10-14", f"prev_day:live-prev-kpi:{after}", "2026-10-14T23:26:08"),
            )


if __name__ == "__main__":
    unittest.main()

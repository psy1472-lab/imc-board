"""Postgres adapter and repository smoke tests."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal

from infrastructure.db.postgres_adapter import _normalize_value, translate_sql


class PostgresAdapterTests(unittest.TestCase):
    def test_translate_insert_or_replace_report_metadata(self) -> None:
        sql = """
            INSERT OR REPLACE INTO report_metadata
            (report_date, center_name) VALUES (?, ?)
        """
        translated = translate_sql(sql)
        self.assertIn("ON CONFLICT (report_date)", translated)
        self.assertNotIn("INSERT OR REPLACE", translated)
        self.assertIn("%s", translated)

    def test_translate_operation_period_returning(self) -> None:
        sql = """
            INSERT INTO operation_period (period_type, start_date, end_date, note, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        translated = translate_sql(sql)
        self.assertIn("RETURNING id", translated)

    def test_normalize_decimal_to_float(self) -> None:
        self.assertEqual(_normalize_value(Decimal("308.5")), 308.5)
        self.assertIsInstance(_normalize_value(Decimal("12.0")), float)


@unittest.skipUnless(
    os.getenv("DATABASE_URL", "").startswith("postgres"),
    "DATABASE_URL postgres required",
)
class PostgresRepositoryIntegrationTests(unittest.TestCase):
    def test_health_and_list_dates(self) -> None:
        from infrastructure.db.repository_factory import create_repository

        repo = create_repository()
        health = repo.get_health_status()
        self.assertEqual(health["database"], "postgres")
        dates = repo.list_report_dates()
        self.assertIsInstance(dates, list)


if __name__ == "__main__":
    unittest.main()

"""Postgres adapter and repository smoke tests."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal

from infrastructure.db.postgres_adapter import (
    PgConnection,
    _as_json_param,
    _normalize_value,
    adapt_params,
    translate_sql,
)


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

    def test_returning_insert_keeps_id_without_mutating_cursor(self) -> None:
        class SlotsCursor:
            __slots__ = ("rowcount", "_rows")

            def __init__(self) -> None:
                self.rowcount = 1
                self._rows = [{"id": 21}]

            def execute(self, sql: str, params: tuple) -> None:
                return None

            def fetchone(self) -> dict | None:
                if not self._rows:
                    return None
                return self._rows.pop(0)

            def fetchall(self) -> list:
                return []

        class FakeConnection:
            def cursor(self, row_factory=None):
                return SlotsCursor()

        result = PgConnection(FakeConnection()).execute(
            """
            INSERT INTO operation_period (period_type, start_date, end_date, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("harvest_season", "2025-11-03", "2025-12-31", None, "2026-10-20"),
        )
        self.assertEqual(result.lastrowid, 21)

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

    def test_adapt_daily_summary_raw_values_as_json(self) -> None:
        sql = "INSERT INTO daily_summary (report_date, raw_values) VALUES (%s, %s)"
        params = ("2026-09-08", '{"total_volume": "37.6만"}')
        adapted = adapt_params(sql, params)
        self.assertEqual(adapted[0], "2026-09-08")
        dumped = _as_json_param({"total_volume": "37.6만"})
        self.assertEqual(type(adapted[1]).__name__, type(dumped).__name__)

    def test_serial_sync_sql_uses_max_id(self) -> None:
        from infrastructure.db.postgres_repository import PostgresRepository

        sql = PostgresRepository.serial_sync_sql("anomaly")
        self.assertIn("pg_get_serial_sequence('anomaly', 'id')", sql)
        self.assertIn("MAX(id) FROM anomaly", sql)
        with self.assertRaises(ValueError):
            PostgresRepository.serial_sync_sql("daily_summary")


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

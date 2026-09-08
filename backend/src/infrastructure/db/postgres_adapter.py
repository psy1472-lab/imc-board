"""psycopg connection wrapper compatible with SqliteRepository SQL patterns."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


class PgRow:
    """Row supporting both name and index access like sqlite3.Row."""

    __slots__ = ("_values", "_keys")

    def __init__(self, record: dict[str, Any]) -> None:
        self._keys = list(record.keys())
        self._values = [_normalize_value(record[key]) for key in self._keys]

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        index = self._keys.index(key)
        return self._values[index]

    def keys(self) -> list[str]:
        return list(self._keys)


class PgExecuteResult:
    __slots__ = ("_cursor", "lastrowid", "rowcount")

    def __init__(self, cursor: psycopg.Cursor) -> None:
        self._cursor = cursor
        self.lastrowid = getattr(cursor, "_imc_lastrowid", None)
        self.rowcount = cursor.rowcount

    def fetchone(self) -> PgRow | None:
        row = self._cursor.fetchone()
        return PgRow(row) if row else None

    def fetchall(self) -> list[PgRow]:
        return [PgRow(row) for row in self._cursor.fetchall()]


_UPSERT_SUFFIX: dict[str, str] = {
    "report_metadata": """
        ON CONFLICT (report_date) DO UPDATE SET
            center_name = EXCLUDED.center_name,
            report_format = EXCLUDED.report_format,
            day_type = EXCLUDED.day_type,
            file_path = EXCLUDED.file_path,
            ingested_at = EXCLUDED.ingested_at
    """,
    "daily_summary": """
        ON CONFLICT (report_date) DO UPDATE SET
            center_name = EXCLUDED.center_name,
            national_volume = EXCLUDED.national_volume,
            total_volume = EXCLUDED.total_volume,
            dispatch_volume = EXCLUDED.dispatch_volume,
            arrival_volume = EXCLUDED.arrival_volume,
            remaining_volume = EXCLUDED.remaining_volume,
            productivity = EXCLUDED.productivity,
            ips_rate = EXCLUDED.ips_rate,
            last_operation_time = EXCLUDED.last_operation_time,
            communication_status = EXCLUDED.communication_status,
            raw_values = EXCLUDED.raw_values
    """,
    "quota_exchange": """
        ON CONFLICT (report_date) DO UPDATE SET
            quarter_standard = EXCLUDED.quarter_standard,
            quarter_actual = EXCLUDED.quarter_actual,
            quarter_difference = EXCLUDED.quarter_difference,
            exchange_standard = EXCLUDED.exchange_standard,
            exchange_actual = EXCLUDED.exchange_actual,
            exchange_difference = EXCLUDED.exchange_difference,
            exchange_remaining = EXCLUDED.exchange_remaining
    """,
    "sorting_machine": """
        ON CONFLICT (report_date) DO UPDATE SET
            total_supply = EXCLUDED.total_supply,
            total_sorted = EXCLUDED.total_sorted,
            sorting_rate = EXCLUDED.sorting_rate,
            ips_rate = EXCLUDED.ips_rate,
            reject_rate = EXCLUDED.reject_rate,
            shortcut_rate = EXCLUDED.shortcut_rate,
            avg_throughput = EXCLUDED.avg_throughput,
            peak_throughput = EXCLUDED.peak_throughput,
            unread_count = EXCLUDED.unread_count,
            unread_rate = EXCLUDED.unread_rate
    """,
}


def translate_sql(sql: str) -> str:
    translated = sql
    match = re.search(r"INSERT OR REPLACE INTO\s+(\w+)", translated, flags=re.IGNORECASE)
    if match:
        table = match.group(1)
        translated = re.sub(
            r"INSERT OR REPLACE INTO\s+" + table,
            f"INSERT INTO {table}",
            translated,
            count=1,
            flags=re.IGNORECASE,
        )
        suffix = _UPSERT_SUFFIX.get(table)
        if suffix:
            translated = translated.rstrip() + suffix

    if re.search(
        r"INSERT INTO\s+operation_period\s+\(period_type,\s*start_date,\s*end_date,\s*note,\s*created_at\)",
        translated,
        flags=re.IGNORECASE,
    ):
        translated = translated.rstrip() + " RETURNING id"

    return translated.replace("?", "%s")


def adapt_params(sql: str, params: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    adapted = list(params)
    if "daily_summary" in sql and "raw_values" in sql and adapted:
        raw_index = 11 if len(adapted) >= 12 else len(adapted) - 1
        value = adapted[raw_index]
        if isinstance(value, str):
            try:
                adapted[raw_index] = json.loads(value)
            except json.JSONDecodeError:
                pass
    if "validation_log" in sql and len(adapted) >= 4:
        details = adapted[3]
        if isinstance(details, str):
            try:
                adapted[3] = json.loads(details)
            except json.JSONDecodeError:
                pass
    return tuple(adapted)


class PgConnection:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] | None = None,
    ) -> PgExecuteResult:
        translated = translate_sql(sql)
        bound = adapt_params(translated, params or ())
        cursor = self._conn.cursor(row_factory=dict_row)
        cursor.execute(translated, bound)
        if "RETURNING id" in translated:
            row = cursor.fetchone()
            if row:
                cursor._imc_lastrowid = row["id"]  # type: ignore[attr-defined]
        return PgExecuteResult(cursor)

    def commit(self) -> None:
        self._conn.commit()

    def __enter__(self) -> PgConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()


def connect_postgres(database_url: str) -> PgConnection:
    conn = psycopg.connect(database_url, row_factory=dict_row)
    return PgConnection(conn)

from __future__ import annotations

from infrastructure.db.postgres_adapter import connect_postgres
from infrastructure.db.sqlite_repository import SqliteRepository


class PostgresRepository(SqliteRepository):
    """PostgreSQL backend reusing SqliteRepository query logic via adapter."""

    _SERIAL_ID_TABLES = ("anomaly", "validation_log", "operation_period")

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.db_path = database_url

    def _init_schema(self) -> None:
        return

    def _connect(self):
        return connect_postgres(self.database_url)

    def save_report(self, path: str, report) -> None:
        self._sync_serial_sequences()
        super().save_report(path, report)

    def create_operation_period(self, payload: dict) -> dict:
        self._sync_serial_sequences()
        return super().create_operation_period(payload)

    def _sync_serial_sequences(self) -> None:
        with self._connect() as conn:
            for table in self._SERIAL_ID_TABLES:
                conn.execute(self.serial_sync_sql(table))

    @classmethod
    def serial_sync_sql(cls, table: str) -> str:
        if table not in cls._SERIAL_ID_TABLES:
            raise ValueError(f"unsupported serial table: {table}")
        return (
            f"SELECT setval("
            f"pg_get_serial_sequence('{table}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
            f"COALESCE((SELECT MAX(id) FROM {table}), 0) > 0)"
        )

    def get_health_status(self) -> dict:
        status = super().get_health_status()
        status["database"] = "postgres"
        status["path"] = self.database_url.split("@")[-1]
        status["migrations"] = ["imc_dashboard_initial (Supabase)"]
        return status

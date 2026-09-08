from __future__ import annotations

from infrastructure.db.postgres_adapter import connect_postgres
from infrastructure.db.sqlite_repository import SqliteRepository


class PostgresRepository(SqliteRepository):
    """PostgreSQL backend reusing SqliteRepository query logic via adapter."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.db_path = database_url

    def _init_schema(self) -> None:
        return

    def _connect(self):
        return connect_postgres(self.database_url)

    def get_health_status(self) -> dict:
        status = super().get_health_status()
        status["database"] = "postgres"
        status["path"] = self.database_url.split("@")[-1]
        status["migrations"] = ["imc_dashboard_initial (Supabase)"]
        return status

from __future__ import annotations

from infrastructure.config import resolve_database_url
from infrastructure.db.postgres_repository import PostgresRepository
from infrastructure.db.sqlite_repository import SqliteRepository


def create_repository() -> SqliteRepository | PostgresRepository:
    """Return the active report repository."""
    database_url = resolve_database_url()
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        return PostgresRepository(database_url)
    return SqliteRepository(database_url)

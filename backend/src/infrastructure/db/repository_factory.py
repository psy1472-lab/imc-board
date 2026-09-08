from __future__ import annotations

from infrastructure.config import resolve_database_url
from infrastructure.db.sqlite_repository import SqliteRepository


def create_repository() -> SqliteRepository:
    database_url = resolve_database_url()
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        raise NotImplementedError(
            "PostgreSQL repository is not implemented yet. "
            "See docs/supabase-postgres-migration-plan.md"
        )
    return SqliteRepository(database_url)

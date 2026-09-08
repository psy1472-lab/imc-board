from __future__ import annotations

from infrastructure.config import resolve_database_url
from infrastructure.db.sqlite_repository import SqliteRepository


def create_repository() -> SqliteRepository:
    """Return the active report repository.

    SQLite is the production backend today. When ``DATABASE_URL`` points to
    Postgres, ``PostgresRepository`` must be wired in (see
    ``docs/supabase-postgres-migration-plan.md``).
    """
    database_url = resolve_database_url()
    if database_url.startswith("postgres://") or database_url.startswith("postgresql://"):
        raise NotImplementedError(
            "PostgreSQL repository is not implemented yet. "
            "Schema and migrate_sqlite_to_postgres.py are ready. "
            "See docs/supabase-postgres-migration-plan.md"
        )
    return SqliteRepository(database_url)

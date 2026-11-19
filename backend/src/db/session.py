from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Owns the connection pool and hands out one AsyncSession per unit of work.

    Services decide when to commit; this class only guarantees that a failed
    unit of work is rolled back and that every session is closed.
    """

    def __init__(self, database_url: str, **engine_options: Any) -> None:
        self.engine: AsyncEngine = create_async_engine(
            database_url, pool_pre_ping=True, **engine_options
        )
        # Async sessions cannot lazy-load expired attributes, so keep them loaded.
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self.session_factory()
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def ping(self) -> None:
        """Raises if the database cannot be reached."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


_database: Database | None = None


def init_database(database_url: str, **engine_options: Any) -> Database:
    global _database
    _database = Database(database_url, **engine_options)
    return _database


def get_database() -> Database:
    if _database is None:
        raise RuntimeError("Database is not initialized; call init_database() first.")
    return _database


async def close_database() -> None:
    global _database
    if _database is not None:
        await _database.dispose()
        _database = None


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `db: AsyncSession = Depends(get_db_session)`."""
    async with get_database().session() as session:
        yield session

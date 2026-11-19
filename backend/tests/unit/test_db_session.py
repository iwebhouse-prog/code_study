"""Verifies engine/session wiring and session lifecycle without a database (T010)."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine

from src.db import session as db_session
from src.db.session import Database

URL = "postgresql+asyncpg://user:pass@127.0.0.1:5432/example"


def database_with_fake_session() -> tuple[Database, MagicMock]:
    database = Database(URL)
    fake_session = MagicMock()
    fake_session.rollback = AsyncMock()
    fake_session.close = AsyncMock()
    database.session_factory = MagicMock(return_value=fake_session)
    return database, fake_session


class TestDatabaseWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        await db_session.close_database()

    async def test_engine_uses_asyncpg_driver(self) -> None:
        database = Database(URL)
        self.assertIsInstance(database.engine, AsyncEngine)
        self.assertEqual(database.engine.url.drivername, "postgresql+asyncpg")
        await database.dispose()

    async def test_connections_are_pinged_before_use(self) -> None:
        database = Database(URL)
        self.assertTrue(database.engine.pool._pre_ping)
        await database.dispose()

    async def test_engine_options_are_passed_through(self) -> None:
        database = Database(URL, pool_size=3, max_overflow=7)
        self.assertEqual(database.engine.pool.size(), 3)
        self.assertEqual(database.engine.pool._max_overflow, 7)
        await database.dispose()

    async def test_sessions_keep_attributes_after_commit(self) -> None:
        database = Database(URL)
        self.assertFalse(database.session_factory.kw["expire_on_commit"])
        await database.dispose()


class TestSessionLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_session_is_closed_after_success(self) -> None:
        database, fake_session = database_with_fake_session()
        async with database.session() as session:
            self.assertIs(session, fake_session)
        fake_session.rollback.assert_not_awaited()
        fake_session.close.assert_awaited_once()
        await database.dispose()

    async def test_session_is_rolled_back_and_closed_on_error(self) -> None:
        database, fake_session = database_with_fake_session()
        with self.assertRaises(ValueError):
            async with database.session():
                raise ValueError("boom")
        fake_session.rollback.assert_awaited_once()
        fake_session.close.assert_awaited_once()
        await database.dispose()


class TestModuleDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        await db_session.close_database()

    async def test_get_database_before_init_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            db_session.get_database()

    async def test_init_then_get_returns_same_database(self) -> None:
        database = db_session.init_database(URL)
        self.assertIs(db_session.get_database(), database)

    async def test_close_database_resets_state(self) -> None:
        db_session.init_database(URL)
        await db_session.close_database()
        with self.assertRaises(RuntimeError):
            db_session.get_database()

    async def test_close_database_without_init_is_harmless(self) -> None:
        await db_session.close_database()

    async def test_get_db_session_yields_session_from_initialized_database(
        self,
    ) -> None:
        database, fake_session = database_with_fake_session()
        db_session._database = database
        sessions = db_session.get_db_session()
        self.assertIs(await anext(sessions), fake_session)
        with self.assertRaises(StopAsyncIteration):
            await anext(sessions)
        fake_session.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

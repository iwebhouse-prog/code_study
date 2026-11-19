"""Exercises session management against a real PostgreSQL database (T010)."""

import unittest

from sqlalchemy import text

from src.db.session import Database
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    execute_script,
    recreate_test_database,
)

COUNT_NOTES = text("SELECT count(*) FROM notes")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestDatabaseSession(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        execute_script("CREATE TABLE notes (body TEXT NOT NULL)")

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self.database = Database(TEST_DATABASE_URL)
        async with self.database.session() as session:
            await session.execute(text("DELETE FROM notes"))
            await session.commit()

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def count_notes(self) -> int:
        async with self.database.session() as session:
            return int((await session.execute(COUNT_NOTES)).scalar_one())

    async def test_session_runs_queries(self) -> None:
        async with self.database.session() as session:
            result = await session.execute(text("SELECT 1"))
            self.assertEqual(result.scalar_one(), 1)

    async def test_committed_changes_persist(self) -> None:
        async with self.database.session() as session:
            await session.execute(text("INSERT INTO notes VALUES ('kept')"))
            await session.commit()
        self.assertEqual(await self.count_notes(), 1)

    async def test_error_discards_uncommitted_changes(self) -> None:
        with self.assertRaises(RuntimeError):
            async with self.database.session() as session:
                await session.execute(text("INSERT INTO notes VALUES ('lost')"))
                raise RuntimeError("service failed mid-transaction")
        self.assertEqual(await self.count_notes(), 0)

    async def test_connection_is_returned_to_pool(self) -> None:
        async with self.database.session() as session:
            await session.execute(text("SELECT 1"))
        self.assertEqual(self.database.engine.pool.checkedout(), 0)

    async def test_pool_recovers_after_failed_statement(self) -> None:
        with self.assertRaises(Exception):  # noqa: B017 - any DB error
            async with self.database.session() as session:
                await session.execute(text("INSERT INTO notes VALUES (NULL)"))
        self.assertEqual(await self.count_notes(), 0)


if __name__ == "__main__":
    unittest.main()

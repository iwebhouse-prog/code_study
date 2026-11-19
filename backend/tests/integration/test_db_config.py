"""Connects with the real pool settings against PostgreSQL (T011)."""

import unittest

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.db import session as db_session
from src.db.config import DatabaseConfig, connect_database
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestConnectDatabase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncTearDown(self) -> None:
        await db_session.close_database()

    async def test_connects_and_registers_database(self) -> None:
        database = await connect_database(DatabaseConfig(url=TEST_DATABASE_URL))
        self.assertIs(db_session.get_database(), database)
        async with database.session() as session:
            self.assertEqual((await session.execute(text("SELECT 1"))).scalar(), 1)

    async def test_ping_succeeds_against_live_database(self) -> None:
        database = await connect_database(DatabaseConfig(url=TEST_DATABASE_URL))
        await database.ping()

    async def test_slow_query_is_cancelled_by_command_timeout(self) -> None:
        config = DatabaseConfig(url=TEST_DATABASE_URL, command_timeout=0.5)
        database = await connect_database(config)
        with self.assertRaises((DBAPIError, TimeoutError)):
            async with database.session() as session:
                await session.execute(text("SELECT pg_sleep(3)"))


if __name__ == "__main__":
    unittest.main()

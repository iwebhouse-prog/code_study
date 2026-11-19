"""Verifies database settings, pool options and startup retries (T011)."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import OperationalError

from src.db import config as db_config
from src.db.config import DatabaseConfig, DatabaseUnavailableError, connect_database
from src.db.session import Database

URL = "postgresql+asyncpg://user:pass@127.0.0.1:5432/example"


class TestDatabaseConfigFromEnv(unittest.TestCase):
    def test_reads_database_url(self) -> None:
        self.assertEqual(DatabaseConfig.from_env({"DATABASE_URL": URL}).url, URL)

    def test_missing_url_explains_how_to_fix(self) -> None:
        with self.assertRaisesRegex(RuntimeError, r"\.env\.example"):
            DatabaseConfig.from_env({})

    def test_sync_driver_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "postgresql\\+asyncpg"):
            DatabaseConfig.from_env({"DATABASE_URL": "postgresql://u:p@h/db"})

    def test_defaults_follow_chk105(self) -> None:
        config = DatabaseConfig.from_env({"DATABASE_URL": URL})
        self.assertEqual(config.pool_size, 10)
        self.assertEqual(config.pool_size + config.max_overflow, 50)
        self.assertEqual(config.pool_timeout, 30)
        self.assertEqual(config.pool_recycle, 300)
        self.assertEqual(config.command_timeout, 30)

    def test_pool_settings_can_be_overridden(self) -> None:
        config = DatabaseConfig.from_env(
            {
                "DATABASE_URL": URL,
                "DB_POOL_SIZE": "5",
                "DB_MAX_OVERFLOW": "15",
                "DB_POOL_TIMEOUT": "10",
                "DB_POOL_RECYCLE": "60",
                "DB_COMMAND_TIMEOUT": "2.5",
            }
        )
        self.assertEqual(
            (config.pool_size, config.max_overflow, config.pool_timeout),
            (5, 15, 10),
        )
        self.assertEqual((config.pool_recycle, config.command_timeout), (60, 2.5))

    def test_invalid_number_names_the_setting(self) -> None:
        with self.assertRaisesRegex(ValueError, "DB_POOL_SIZE"):
            DatabaseConfig.from_env({"DATABASE_URL": URL, "DB_POOL_SIZE": "ten"})

    def test_non_positive_pool_size_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "DB_POOL_SIZE"):
            DatabaseConfig.from_env({"DATABASE_URL": URL, "DB_POOL_SIZE": "0"})

    def test_reads_process_environment_by_default(self) -> None:
        with (
            patch("src.config.load_dotenv") as load_dotenv,
            patch.dict(os.environ, {"DATABASE_URL": URL}),
        ):
            self.assertEqual(DatabaseConfig.from_env().url, URL)
        load_dotenv.assert_called_once()
        self.assertFalse(load_dotenv.call_args.kwargs["override"])


class TestEngineOptions(unittest.IsolatedAsyncioTestCase):
    async def test_engine_is_built_with_pool_settings(self) -> None:
        config = DatabaseConfig(url=URL)
        database = Database(config.url, **config.engine_options())
        pool = database.engine.pool
        self.assertEqual(pool.size(), 10)
        self.assertEqual(pool._max_overflow, 40)
        self.assertEqual(pool._timeout, 30)
        self.assertEqual(pool._recycle, 300)
        await database.dispose()

    def test_query_timeout_is_passed_to_asyncpg(self) -> None:
        options = DatabaseConfig(url=URL, command_timeout=7).engine_options()
        self.assertEqual(options["connect_args"], {"command_timeout": 7})


def fake_database(ping_side_effect: object) -> MagicMock:
    database = MagicMock(spec=Database)
    database.ping = AsyncMock(side_effect=ping_side_effect)
    database.dispose = AsyncMock()
    return database


DB_DOWN = OperationalError("SELECT 1", {}, Exception("connection refused"))


class TestConnectDatabase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.sleep = AsyncMock()
        self.config = DatabaseConfig(url=URL)

    async def connect(self, database: MagicMock) -> Database:
        with patch.object(db_config, "init_database", return_value=database) as init:
            result = await connect_database(self.config, sleep=self.sleep)
        init.assert_called_once_with(URL, **self.config.engine_options())
        return result

    async def test_returns_database_when_first_ping_succeeds(self) -> None:
        database = fake_database([None])
        self.assertIs(await self.connect(database), database)
        self.sleep.assert_not_awaited()

    async def test_retries_until_database_answers(self) -> None:
        database = fake_database([DB_DOWN, OSError("refused"), None])
        self.assertIs(await self.connect(database), database)
        self.assertEqual(database.ping.await_count, 3)
        self.assertEqual([c.args for c in self.sleep.await_args_list], [(5,), (5,)])

    async def test_gives_up_after_three_attempts(self) -> None:
        database = fake_database([DB_DOWN, DB_DOWN, DB_DOWN])
        with self.assertRaises(DatabaseUnavailableError):
            await self.connect(database)
        self.assertEqual(database.ping.await_count, 3)
        self.assertEqual(self.sleep.await_count, 2)
        database.dispose.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

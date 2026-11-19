"""Checks the User model against the real migrated table (T023)."""

import asyncio
import unittest
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.session import Database
from src.models.user import User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Timestamps are nullable in migration 001 but always filled by their defaults,
# so the model states the stronger NOT NULL guarantee for code that reads them.
STRICTER_IN_MODEL = ("created_at", "updated_at")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestUserMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(User, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestUserPersistence(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self.database = Database(TEST_DATABASE_URL)

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(self, email: str = "learner@example.com") -> User:
        async with self.database.session() as session:
            user = User(email=email, password_hash="$2b$12$hash")
            session.add(user)
            await session.commit()
            return user

    async def test_database_defaults_are_available_after_insert(self) -> None:
        user = await self._add()
        self.assertIsNotNone(user.id)
        self.assertEqual(user.skill_level, "Complete Beginner")
        self.assertIsInstance(user.created_at, datetime)
        self.assertIsInstance(user.updated_at, datetime)
        self.assertIsNone(user.last_login_at)

    async def test_can_be_read_back_by_email(self) -> None:
        saved = await self._add()
        async with self.database.session() as session:
            found = await session.scalar(
                select(User).where(User.email == "learner@example.com")
            )
        assert found is not None
        self.assertEqual(found.id, saved.id)

    async def test_updated_at_is_readable_right_after_update(self) -> None:
        # Async sessions cannot lazy-load, so onupdate values must come back
        # with the UPDATE; otherwise reading the attribute raises MissingGreenlet.
        saved = await self._add()
        await asyncio.sleep(0.01)
        async with self.database.session() as session:
            user = await session.get(User, saved.id)
            assert user is not None
            user.last_login_at = datetime.now(UTC)
            await session.commit()
            self.assertGreater(user.updated_at, saved.updated_at)

    async def test_duplicate_email_is_rejected(self) -> None:
        await self._add()
        with self.assertRaises(IntegrityError):
            await self._add()

    async def test_invalid_email_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "valid_email"):
            await self._add(email="not-an-email")

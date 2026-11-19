"""Checks the RefreshToken model against the real migrated table (T024)."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models.refresh_token import RefreshToken
from src.models.user import User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by their defaults.
STRICTER_IN_MODEL = ("created_at", "revoked")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestRefreshTokenMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(RefreshToken, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestRefreshTokenPersistence(unittest.IsolatedAsyncioTestCase):
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
        async with self.database.session() as session:
            self.user = User(email="learner@example.com", password_hash="hash")
            session.add(self.user)
            await session.commit()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(
        self, token_hash: str = "hash-1", user_id: uuid.UUID | None = None
    ) -> RefreshToken:
        async with self.database.session() as session:
            token = RefreshToken(
                user_id=user_id or self.user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
            session.add(token)
            await session.commit()
            return token

    async def test_database_defaults_are_available_after_insert(self) -> None:
        token = await self._add()
        self.assertIsNotNone(token.id)
        self.assertIs(token.revoked, False)
        self.assertIsNone(token.revoked_at)
        self.assertIsInstance(token.created_at, datetime)

    async def test_revoking_keeps_the_row(self) -> None:
        saved = await self._add()
        async with self.database.session() as session:
            token = await session.get(RefreshToken, saved.id)
            assert token is not None
            token.revoked = True
            token.revoked_at = datetime.now(UTC)
            await session.commit()
        async with self.database.session() as session:
            found = await session.get(RefreshToken, saved.id)
        assert found is not None
        self.assertIs(found.revoked, True)
        self.assertIsNotNone(found.revoked_at)

    async def test_duplicate_hash_is_rejected(self) -> None:
        await self._add("same")
        with self.assertRaises(IntegrityError):
            await self._add("same")

    async def test_unknown_user_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            await self._add(user_id=uuid.uuid4())

    async def test_one_user_can_hold_several_sessions(self) -> None:
        # requirements-addendum: each device has its own refresh token.
        await self._add("phone")
        await self._add("laptop")
        async with self.database.session() as session:
            user = await session.scalar(
                select(User).options(selectinload(User.refresh_tokens))
            )
        assert user is not None
        self.assertEqual(
            {token.token_hash for token in user.refresh_tokens}, {"phone", "laptop"}
        )

    async def test_deleting_a_user_deletes_their_tokens(self) -> None:
        await self._add()
        async with self.database.session() as session:
            user = await session.get(User, self.user.id)
            await session.delete(user)
            await session.commit()
        async with self.database.session() as session:
            remaining = (await session.scalars(select(RefreshToken))).all()
        self.assertEqual(remaining, [])

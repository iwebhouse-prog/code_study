"""Runs TokenService against PostgreSQL (T026)."""

import asyncio
import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from src.db.session import Database
from src.models import RefreshToken, User
from src.services.auth.token_service import (
    SessionExpiredError,
    TokenPair,
    TokenService,
)
from src.services.auth.user_service import UserService
from src.utils.jwt import JWTConfig, create_refresh_token, decode_token
from src.utils.security import hash_token
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
LOGGER = "src.services.auth.token_service"


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestTokenService(unittest.IsolatedAsyncioTestCase):
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
        self.user_id = await self._add_user("learner@example.com")

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add_user(self, email: str) -> uuid.UUID:
        async with self.database.session() as session:
            user = User(email=email, password_hash="hash")
            session.add(user)
            await session.commit()
            return user.id

    async def _issue(
        self, user_id: uuid.UUID | None = None, now: datetime | None = None
    ) -> TokenPair:
        async with self.database.session() as session:
            return await TokenService(session, CONFIG).issue_tokens(
                user_id or self.user_id, now=now
            )

    async def _rotate(self, refresh_token: str) -> TokenPair:
        async with self.database.session() as session:
            return await TokenService(session, CONFIG).rotate(refresh_token)

    async def _row(self, refresh_token: str) -> RefreshToken:
        async with self.database.session() as session:
            row = await session.scalar(
                select(RefreshToken).where(
                    RefreshToken.token_hash == hash_token(refresh_token)
                )
            )
        assert row is not None
        return row

    async def _active_count(self, user_id: uuid.UUID | None = None) -> int:
        async with self.database.session() as session:
            rows = await session.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == (user_id or self.user_id),
                    RefreshToken.revoked.is_(False),
                )
            )
            return len(rows.all())

    async def test_issue_returns_tokens_for_the_user(self) -> None:
        pair = await self._issue()
        self.assertEqual(
            decode_token(pair.access_token, "access", CONFIG).subject, self.user_id
        )
        self.assertEqual(
            decode_token(pair.refresh_token, "refresh", CONFIG).subject, self.user_id
        )

    async def test_only_the_hash_of_the_refresh_token_is_stored(self) -> None:
        pair = await self._issue()
        row = await self._row(pair.refresh_token)
        self.assertNotEqual(row.token_hash, pair.refresh_token)
        self.assertEqual(row.user_id, self.user_id)

    async def test_stored_expiry_is_seven_days_away(self) -> None:
        now = datetime.now(UTC)
        pair = await self._issue(now=now)
        row = await self._row(pair.refresh_token)
        self.assertEqual(row.expires_at, now + timedelta(days=7))

    async def test_each_login_gets_its_own_session(self) -> None:
        first = await self._issue()
        second = await self._issue()
        self.assertNotEqual(first.refresh_token, second.refresh_token)
        self.assertEqual(await self._active_count(), 2)

    async def test_rotate_replaces_the_token(self) -> None:
        old = await self._issue()
        new = await self._rotate(old.refresh_token)
        self.assertNotEqual(new.refresh_token, old.refresh_token)
        old_row = await self._row(old.refresh_token)
        self.assertIs(old_row.revoked, True)
        self.assertIsNotNone(old_row.revoked_at)
        self.assertIs((await self._row(new.refresh_token)).revoked, False)
        self.assertEqual(await self._active_count(), 1)

    async def test_rotated_token_keeps_working_in_a_chain(self) -> None:
        pair = await self._issue()
        for _ in range(3):
            pair = await self._rotate(pair.refresh_token)
        self.assertEqual(await self._active_count(), 1)

    async def test_reusing_a_used_token_ends_every_session_of_that_user(self) -> None:
        # Two people holding one token means it was stolen; only ending all
        # sessions removes a thief who rotated first.
        other_device = await self._issue()
        stolen = await self._issue()
        rotated = await self._rotate(stolen.refresh_token)
        with self.assertRaises(SessionExpiredError):
            await self._rotate(stolen.refresh_token)
        self.assertEqual(await self._active_count(), 0)
        for pair in (rotated, other_device):
            with self.assertRaises(SessionExpiredError):
                await self._rotate(pair.refresh_token)

    async def test_reuse_leaves_other_users_alone(self) -> None:
        other_user = await self._add_user("other@example.com")
        await self._issue(other_user)
        stolen = await self._issue()
        await self._rotate(stolen.refresh_token)
        with self.assertRaises(SessionExpiredError):
            await self._rotate(stolen.refresh_token)
        self.assertEqual(await self._active_count(other_user), 1)

    async def test_simultaneous_rotations_never_give_two_new_sessions(self) -> None:
        pair = await self._issue()
        results = await asyncio.gather(
            self._rotate(pair.refresh_token),
            self._rotate(pair.refresh_token),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(r, TokenPair) for r in results), 1)
        self.assertEqual(sum(isinstance(r, SessionExpiredError) for r in results), 1)
        self.assertEqual(await self._active_count(), 0)

    async def test_expired_refresh_token_is_refused(self) -> None:
        pair = await self._issue(now=datetime.now(UTC) - timedelta(days=8))
        with self.assertRaises(SessionExpiredError):
            await self._rotate(pair.refresh_token)

    async def test_access_token_cannot_be_used_to_rotate(self) -> None:
        pair = await self._issue()
        with self.assertRaises(SessionExpiredError):
            await self._rotate(pair.access_token)

    async def test_garbage_is_refused(self) -> None:
        with self.assertRaises(SessionExpiredError):
            await self._rotate("not-a-jwt")

    async def test_valid_token_that_was_never_stored_is_refused(self) -> None:
        unknown = create_refresh_token(self.user_id, CONFIG)
        with self.assertRaises(SessionExpiredError):
            await self._rotate(unknown)

    async def test_revoke_all_counts_and_ends_only_active_sessions(self) -> None:
        await self._issue()
        await self._issue()
        rotated = await self._issue()
        await self._rotate(rotated.refresh_token)
        async with self.database.session() as session:
            count = await TokenService(session, CONFIG).revoke_all(self.user_id)
        self.assertEqual(count, 3)
        self.assertEqual(await self._active_count(), 0)

    async def test_revoke_all_keeps_the_original_time_of_old_revocations(self) -> None:
        old = await self._issue()
        await self._rotate(old.refresh_token)
        first = (await self._row(old.refresh_token)).revoked_at
        async with self.database.session() as session:
            await TokenService(session, CONFIG).revoke_all(self.user_id)
        self.assertEqual((await self._row(old.refresh_token)).revoked_at, first)

    async def test_logout_revokes_a_token_from_this_service(self) -> None:
        pair = await self._issue()
        async with self.database.session() as session:
            await UserService(session).logout(pair.refresh_token)
        with self.assertRaises(SessionExpiredError):
            await self._rotate(pair.refresh_token)

    async def test_events_are_logged_without_token_values(self) -> None:
        with self.assertLogs(LOGGER, "INFO") as logs:
            pair = await self._issue()
            await self._rotate(pair.refresh_token)
            with self.assertRaises(SessionExpiredError):
                await self._rotate(pair.refresh_token)
            with self.assertRaises(SessionExpiredError):
                await self._rotate("not-a-jwt")
        output = "\n".join(logs.output)
        for event in ("token_rotated", "token_reuse_detected", "token_refresh_failed"):
            self.assertIn(event, output)
        self.assertNotIn(pair.refresh_token, output)
        self.assertNotIn(hash_token(pair.refresh_token), output)

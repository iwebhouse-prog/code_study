"""Runs UserService against PostgreSQL (T025)."""

import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import select

from src.db.session import Database
from src.models import RefreshToken, User
from src.services.auth import user_service
from src.services.auth.user_service import (
    EmailTakenError,
    InvalidCredentialsError,
    UserService,
)
from src.utils.security import hash_token, verify_password
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

EMAIL = "learner@example.com"
PASSWORD = "testpass123"
LOGGER = "src.services.auth.user_service"


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestUserService(unittest.IsolatedAsyncioTestCase):
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

    async def _register(self, email: str = EMAIL, password: str = PASSWORD) -> User:
        async with self.database.session() as session:
            return await UserService(session).register(email, password)

    async def _login(self, email: str = EMAIL, password: str = PASSWORD) -> User:
        async with self.database.session() as session:
            return await UserService(session).login(email, password)

    async def _stored_user(self) -> User:
        async with self.database.session() as session:
            user = await session.scalar(select(User))
        assert user is not None
        return user

    async def _add_token(self, user: User, token: str) -> None:
        async with self.database.session() as session:
            session.add(
                RefreshToken(
                    user_id=user.id,
                    token_hash=hash_token(token),
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
            )
            await session.commit()

    async def _stored_token(self, token: str) -> RefreshToken:
        async with self.database.session() as session:
            found = await session.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
            )
        assert found is not None
        return found

    async def test_register_saves_a_normalized_user_with_a_hashed_password(
        self,
    ) -> None:
        user = await self._register("  Learner@Example.COM ")
        stored = await self._stored_user()
        self.assertEqual(stored.id, user.id)
        self.assertEqual(stored.email, EMAIL)
        self.assertEqual(stored.skill_level, "Complete Beginner")
        self.assertNotIn(PASSWORD, stored.password_hash)
        self.assertTrue(verify_password(PASSWORD, stored.password_hash))

    async def test_duplicate_email_is_refused_whatever_the_case(self) -> None:
        await self._register()
        with self.assertRaises(EmailTakenError):
            await self._register("LEARNER@example.com")

    async def test_simultaneous_registrations_create_one_account(self) -> None:
        results = await asyncio.gather(
            self._register(), self._register(), return_exceptions=True
        )
        self.assertEqual(sum(isinstance(r, User) for r in results), 1)
        self.assertEqual(sum(isinstance(r, EmailTakenError) for r in results), 1)

    async def test_login_returns_the_user_and_records_the_time(self) -> None:
        registered = await self._register()
        before = datetime.now(UTC)
        user = await self._login("LEARNER@example.com")
        self.assertEqual(user.id, registered.id)
        stored = await self._stored_user()
        assert stored.last_login_at is not None
        self.assertGreaterEqual(stored.last_login_at, before)

    async def test_wrong_password_is_refused_and_records_nothing(self) -> None:
        await self._register()
        with self.assertRaises(InvalidCredentialsError):
            await self._login(password="wrongpass123")
        self.assertIsNone((await self._stored_user()).last_login_at)

    async def test_unknown_email_gets_the_same_error_as_a_wrong_password(self) -> None:
        await self._register()
        with self.assertRaises(InvalidCredentialsError) as wrong_password:
            await self._login(password="wrongpass123")
        with self.assertRaises(InvalidCredentialsError) as unknown_email:
            await self._login(email="nobody@example.com")
        self.assertEqual(wrong_password.exception.error, unknown_email.exception.error)
        self.assertEqual(
            wrong_password.exception.message, unknown_email.exception.message
        )

    async def test_unknown_email_still_runs_a_password_check(self) -> None:
        # Otherwise the faster answer reveals which emails have accounts.
        with (
            patch.object(user_service, "verify_password", wraps=verify_password) as spy,
            self.assertRaises(InvalidCredentialsError),
        ):
            await self._login(email="nobody@example.com")
        spy.assert_called_once()

    async def test_password_hashing_does_not_block_other_requests(self) -> None:
        await self._register()
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(ticker())
        await self._login()
        task.cancel()
        # bcrypt takes about 0.2 seconds; a blocked event loop would not tick.
        self.assertGreaterEqual(ticks, 5)

    async def test_logout_revokes_only_that_session(self) -> None:
        user = await self._register()
        await self._add_token(user, "phone")
        await self._add_token(user, "laptop")
        async with self.database.session() as session:
            await UserService(session).logout("phone")
        phone = await self._stored_token("phone")
        laptop = await self._stored_token("laptop")
        self.assertIs(phone.revoked, True)
        self.assertIsNotNone(phone.revoked_at)
        self.assertIs(laptop.revoked, False)

    async def test_logout_with_an_unknown_token_does_nothing(self) -> None:
        async with self.database.session() as session:
            await UserService(session).logout("never-issued")

    async def test_logging_out_twice_keeps_the_first_time(self) -> None:
        user = await self._register()
        await self._add_token(user, "phone")
        async with self.database.session() as session:
            await UserService(session).logout("phone")
        first = (await self._stored_token("phone")).revoked_at
        async with self.database.session() as session:
            await UserService(session).logout("phone")
        self.assertEqual((await self._stored_token("phone")).revoked_at, first)

    async def test_security_events_are_logged_without_secrets(self) -> None:
        with self.assertLogs(LOGGER, "INFO") as logs:
            user = await self._register()
            await self._login()
            with self.assertRaises(InvalidCredentialsError):
                await self._login(password="wrongpass123")
            await self._add_token(user, "secret-token-value")
            async with self.database.session() as session:
                await UserService(session).logout("secret-token-value")
        output = "\n".join(logs.output)
        for event in ("user_registered", "login_succeeded", "login_failed", "logout"):
            self.assertIn(event, output)
        for secret in (PASSWORD, "wrongpass123", "secret-token-value", EMAIL):
            self.assertNotIn(secret, output)
        self.assertIn("l***@example.com", output)

"""Verifies the route protection dependency without a database (T027)."""

import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.api.dependencies import ACCESS_TOKEN_COOKIE, get_current_user
from src.api.exceptions import UnauthorizedError
from src.models import User
from src.services.auth.token_service import (
    AccessTokenExpiredError,
    SessionExpiredError,
)

USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestGetCurrentUser(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.token_service = MagicMock()
        self.token_service.verify_access_token.return_value = USER_ID
        self.user = User(id=USER_ID, email="a@example.com", password_hash="x")
        self.user_service = MagicMock()
        self.user_service.get_by_id = AsyncMock(return_value=self.user)

    async def _call(self, token: str | None = "token") -> User:
        return await get_current_user(self.token_service, self.user_service, token)

    def test_cookie_name(self) -> None:
        self.assertEqual(ACCESS_TOKEN_COOKIE, "access_token")

    async def test_returns_the_user_of_a_valid_token(self) -> None:
        self.assertIs(await self._call("good"), self.user)
        self.token_service.verify_access_token.assert_called_once_with("good")
        self.user_service.get_by_id.assert_awaited_once_with(USER_ID)

    async def test_missing_cookie_asks_to_sign_in(self) -> None:
        with self.assertRaises(UnauthorizedError):
            await self._call(None)
        self.token_service.verify_access_token.assert_not_called()

    async def test_empty_cookie_asks_to_sign_in(self) -> None:
        with self.assertRaises(UnauthorizedError):
            await self._call("")

    async def test_expired_token_error_reaches_the_client(self) -> None:
        self.token_service.verify_access_token.side_effect = AccessTokenExpiredError()
        with self.assertRaises(AccessTokenExpiredError):
            await self._call()
        self.user_service.get_by_id.assert_not_called()

    async def test_invalid_token_error_reaches_the_client(self) -> None:
        self.token_service.verify_access_token.side_effect = SessionExpiredError()
        with self.assertRaises(SessionExpiredError):
            await self._call()

    async def test_deleted_user_ends_the_session(self) -> None:
        self.user_service.get_by_id.return_value = None
        with self.assertRaises(SessionExpiredError):
            await self._call()

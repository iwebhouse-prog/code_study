"""Verifies access token checks and token errors without a database (T026)."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.api.error_messages import ERROR_MESSAGES
from src.models import RefreshToken
from src.services.auth.token_service import (
    AccessTokenExpiredError,
    SessionExpiredError,
    TokenService,
)
from src.utils.jwt import JWTConfig, create_access_token, create_refresh_token

CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestErrors(unittest.TestCase):
    def test_session_expired_means_sign_in_again(self) -> None:
        error = SessionExpiredError()
        self.assertEqual((error.status_code, error.error), (401, "session_expired"))
        self.assertEqual(error.message, ERROR_MESSAGES["session_expired"])

    def test_expired_access_token_has_its_own_code(self) -> None:
        # The frontend refreshes silently on this code (T038) and only sends
        # the user back to the login page on session_expired.
        error = AccessTokenExpiredError()
        self.assertEqual((error.status_code, error.error), (401, "token_expired"))
        self.assertEqual(error.message, ERROR_MESSAGES["token_expired"])


class TestVerifyAccessToken(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TokenService(MagicMock(), CONFIG)

    def test_returns_the_user_id(self) -> None:
        token = create_access_token(USER_ID, CONFIG)
        self.assertEqual(self.service.verify_access_token(token), USER_ID)

    def test_expired_token_asks_for_a_refresh(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=16)
        token = create_access_token(USER_ID, CONFIG, now=past)
        with self.assertRaises(AccessTokenExpiredError):
            self.service.verify_access_token(token)

    def test_garbage_is_a_session_error(self) -> None:
        with self.assertRaises(SessionExpiredError):
            self.service.verify_access_token("not-a-jwt")

    def test_refresh_token_is_not_an_access_token(self) -> None:
        with self.assertRaises(SessionExpiredError):
            self.service.verify_access_token(create_refresh_token(USER_ID, CONFIG))


class TestRevokeOnModel(unittest.TestCase):
    def test_sets_the_flag_and_the_time_together(self) -> None:
        token = RefreshToken(revoked=False)
        before = datetime.now(UTC)
        token.revoke()
        self.assertIs(token.revoked, True)
        assert token.revoked_at is not None
        self.assertGreaterEqual(token.revoked_at, before)

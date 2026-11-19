"""Verifies input rules of UserService without a database (T025)."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from src.api.error_messages import ERROR_MESSAGES
from src.api.exceptions import AppError, FieldValidationError
from src.services.auth.user_service import (
    EmailTakenError,
    InvalidCredentialsError,
    UserService,
    mask_email,
    normalize_email,
)
from src.utils.security import hash_token


class TestNormalizeEmail(unittest.TestCase):
    def test_trims_and_lowercases(self) -> None:
        self.assertEqual(
            normalize_email("  Student@Example.COM "), "student@example.com"
        )


class TestMaskEmail(unittest.TestCase):
    def test_hides_the_local_part(self) -> None:
        self.assertEqual(mask_email("learner@example.com"), "l***@example.com")

    def test_text_without_at_sign_is_fully_hidden(self) -> None:
        self.assertEqual(mask_email("not-an-email"), "***")


class TestFieldValidationError(unittest.TestCase):
    def test_uses_the_shape_the_frontend_reads(self) -> None:
        error = FieldValidationError("email", "올바른 이메일 형식이 아닙니다.")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error, "validation_error")
        self.assertEqual(error.message, ERROR_MESSAGES["validation_error"])
        self.assertEqual(
            error.details,
            {
                "fields": [
                    {"field": "email", "message": "올바른 이메일 형식이 아닙니다."}
                ]
            },
        )


class TestAuthErrors(unittest.TestCase):
    def test_email_taken_is_conflict(self) -> None:
        error = EmailTakenError()
        self.assertIsInstance(error, AppError)
        self.assertEqual((error.status_code, error.error), (409, "email_taken"))
        self.assertEqual(error.message, ERROR_MESSAGES["email_taken"])

    def test_invalid_credentials_is_unauthorized(self) -> None:
        error = InvalidCredentialsError()
        self.assertEqual((error.status_code, error.error), (401, "invalid_credentials"))
        self.assertEqual(error.message, ERROR_MESSAGES["invalid_credentials"])


class TestRegisterValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.service = UserService(self.session)

    async def assert_rejected(self, email: str, password: str, field: str) -> None:
        with self.assertRaises(FieldValidationError) as caught:
            await self.service.register(email, password)
        assert caught.exception.details is not None
        self.assertEqual(caught.exception.details["fields"][0]["field"], field)
        self.session.add.assert_not_called()

    async def test_invalid_emails_are_rejected(self) -> None:
        for email in (
            "",
            "   ",
            "no-at-sign",
            "a@b",
            "a@b.c",
            "two@@example.com",
            "pipe@example.c|m",
            "spaces in@example.com",
            f"{'a' * 250}@example.com",
        ):
            with self.subTest(email=email):
                await self.assert_rejected(email, "testpass123", "email")

    async def test_short_password_is_rejected(self) -> None:
        await self.assert_rejected("a@example.com", "abc1234", "password")

    async def test_password_without_digit_is_rejected(self) -> None:
        await self.assert_rejected("a@example.com", "abcdefgh", "password")

    async def test_password_without_letter_is_rejected(self) -> None:
        await self.assert_rejected("a@example.com", "12345678", "password")

    async def test_password_over_bcrypt_limit_is_rejected(self) -> None:
        await self.assert_rejected("a@example.com", "a1" * 37, "password")

    async def test_korean_password_counts_bytes_for_the_limit(self) -> None:
        await self.assert_rejected("a@example.com", "가" * 24 + "1", "password")


class TestHashToken(unittest.TestCase):
    def test_is_sha256_hex(self) -> None:
        # data-model.md: refresh_tokens.token_hash is a SHA-256 hash.
        self.assertEqual(
            hash_token("abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        )

    def test_never_contains_the_token(self) -> None:
        self.assertNotIn("my-refresh-token", hash_token("my-refresh-token"))

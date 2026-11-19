"""Verifies bcrypt password hashing and verification (T013)."""

import unittest

import bcrypt

from src.utils.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    hash_password,
    verify_password,
)

PASSWORD = "testpass123"


class TestHashPassword(unittest.TestCase):
    def test_hash_uses_bcrypt_cost_12(self) -> None:
        # research.md section 8 / data-model.md: bcrypt with cost factor 12.
        self.assertTrue(hash_password(PASSWORD).startswith("$2b$12$"))

    def test_hash_fits_password_hash_column(self) -> None:
        # users.password_hash is VARCHAR(255).
        self.assertLessEqual(len(hash_password(PASSWORD)), 255)

    def test_hash_does_not_contain_plain_password(self) -> None:
        self.assertNotIn(PASSWORD, hash_password(PASSWORD))

    def test_same_password_gets_different_salt(self) -> None:
        self.assertNotEqual(hash_password(PASSWORD), hash_password(PASSWORD))

    def test_empty_password_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("")

    def test_password_over_72_bytes_is_rejected(self) -> None:
        # bcrypt only reads 72 bytes; longer input must not be silently cut.
        with self.assertRaisesRegex(PasswordTooLongError, "72"):
            hash_password("a" * (BCRYPT_MAX_PASSWORD_BYTES + 1))

    def test_limit_counts_bytes_not_characters(self) -> None:
        # Korean syllables are 3 bytes in UTF-8: 24 fit, 25 do not.
        hash_password("가" * 24)
        with self.assertRaises(PasswordTooLongError):
            hash_password("가" * 25)

    def test_too_long_error_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(PasswordTooLongError, ValueError))


class TestVerifyPassword(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hashed = hash_password(PASSWORD)

    def test_correct_password_matches(self) -> None:
        self.assertTrue(verify_password(PASSWORD, self.hashed))

    def test_wrong_password_does_not_match(self) -> None:
        for wrong in ("testpass124", "TESTPASS123", "testpass123 ", ""):
            with self.subTest(wrong=wrong):
                self.assertFalse(verify_password(wrong, self.hashed))

    def test_unicode_password_round_trip(self) -> None:
        password = "비밀번호123!"
        self.assertTrue(verify_password(password, hash_password(password)))

    def test_password_at_byte_limit_round_trip(self) -> None:
        password = "a" * BCRYPT_MAX_PASSWORD_BYTES
        self.assertTrue(verify_password(password, hash_password(password)))

    def test_too_long_login_attempt_is_false_not_error(self) -> None:
        # A login form must answer "wrong password", not crash with 500.
        attempt = PASSWORD + "x" * BCRYPT_MAX_PASSWORD_BYTES
        self.assertFalse(verify_password(attempt, self.hashed))

    def test_hash_from_other_bcrypt_cost_still_verifies(self) -> None:
        # Hashes created with another cost (e.g. seed data) stay valid.
        old = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()
        self.assertTrue(verify_password(PASSWORD, old))

    def test_malformed_hash_raises(self) -> None:
        # A broken stored hash is a data bug and must not look like "wrong password".
        with self.assertRaises(ValueError):
            verify_password(PASSWORD, "not-a-bcrypt-hash")

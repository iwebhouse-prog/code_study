"""Verifies JWT access/refresh token creation and verification (T012)."""

import os
import unittest
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt

from src.utils.jwt import (
    InvalidTokenError,
    JWTConfig,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
)

ACCESS_SECRET = "a" * 32
REFRESH_SECRET = "r" * 32
ENV = {"JWT_SECRET_KEY": ACCESS_SECRET, "JWT_REFRESH_SECRET": REFRESH_SECRET}
CONFIG = JWTConfig(access_secret=ACCESS_SECRET, refresh_secret=REFRESH_SECRET)
USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestJWTConfigFromEnv(unittest.TestCase):
    def test_defaults_follow_research(self) -> None:
        config = JWTConfig.from_env(ENV)
        self.assertEqual(config.algorithm, "HS256")
        self.assertEqual(config.access_token_expire, timedelta(minutes=15))
        self.assertEqual(config.refresh_token_expire, timedelta(days=7))

    def test_settings_can_be_overridden(self) -> None:
        config = JWTConfig.from_env(
            {
                "JWT_SECRET_KEY": "a" * 64,
                "JWT_REFRESH_SECRET": "r" * 64,
                "JWT_ALGORITHM": "HS512",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "5",
                "REFRESH_TOKEN_EXPIRE_DAYS": "1",
            }
        )
        self.assertEqual(config.algorithm, "HS512")
        self.assertEqual(config.access_token_expire, timedelta(minutes=5))
        self.assertEqual(config.refresh_token_expire, timedelta(days=1))

    def test_missing_secret_explains_how_to_fix(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "JWT_SECRET_KEY.*openssl"):
            JWTConfig.from_env({"JWT_REFRESH_SECRET": REFRESH_SECRET})

    def test_short_secret_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "JWT_REFRESH_SECRET.*32"):
            JWTConfig.from_env({**ENV, "JWT_REFRESH_SECRET": "short"})

    def test_longer_hash_needs_longer_secret(self) -> None:
        # 32 characters is enough for HS256 but not for HS512 (64 bytes).
        with self.assertRaisesRegex(ValueError, "JWT_SECRET_KEY.*64"):
            JWTConfig.from_env({**ENV, "JWT_ALGORITHM": "HS512"})

    def test_example_placeholder_secret_is_rejected(self) -> None:
        placeholder = "change-me-access-token-secret-padding"
        with self.assertRaisesRegex(ValueError, "JWT_SECRET_KEY"):
            JWTConfig.from_env({**ENV, "JWT_SECRET_KEY": placeholder})

    def test_same_secret_for_both_tokens_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "different"):
            JWTConfig.from_env({**ENV, "JWT_REFRESH_SECRET": ACCESS_SECRET})

    def test_non_hmac_algorithm_is_rejected(self) -> None:
        for algorithm in ("none", "RS256"):
            with self.subTest(algorithm=algorithm), self.assertRaises(ValueError):
                JWTConfig.from_env({**ENV, "JWT_ALGORITHM": algorithm})

    def test_invalid_expiry_names_the_setting(self) -> None:
        for raw in ("soon", "0"):
            with (
                self.subTest(raw=raw),
                self.assertRaisesRegex(ValueError, "ACCESS_TOKEN_EXPIRE_MINUTES"),
            ):
                JWTConfig.from_env({**ENV, "ACCESS_TOKEN_EXPIRE_MINUTES": raw})

    def test_reads_process_environment_by_default(self) -> None:
        with (
            patch("src.config.load_dotenv") as load_dotenv,
            patch.dict(os.environ, ENV),
        ):
            self.assertEqual(JWTConfig.from_env().access_secret, ACCESS_SECRET)
        load_dotenv.assert_called_once()
        self.assertFalse(load_dotenv.call_args.kwargs["override"])


class TestCreateAndDecode(unittest.TestCase):
    def test_access_token_round_trip(self) -> None:
        now = datetime.now(UTC).replace(microsecond=0)
        payload = decode_token(
            create_access_token(USER_ID, CONFIG, now=now), "access", CONFIG
        )
        self.assertEqual(payload.subject, USER_ID)
        self.assertEqual(payload.token_type, "access")
        self.assertEqual(payload.issued_at, now)
        self.assertEqual(payload.expires_at, now + timedelta(minutes=15))

    def test_refresh_token_round_trip(self) -> None:
        now = datetime.now(UTC).replace(microsecond=0)
        payload = decode_token(
            create_refresh_token(USER_ID, CONFIG, now=now), "refresh", CONFIG
        )
        self.assertEqual(payload.subject, USER_ID)
        self.assertEqual(payload.token_type, "refresh")
        self.assertEqual(payload.expires_at, now + timedelta(days=7))

    def test_each_token_is_unique(self) -> None:
        # refresh_tokens.token_hash is UNIQUE, so two logins in the same
        # second must still produce different tokens.
        now = datetime.now(UTC)
        first = create_refresh_token(USER_ID, CONFIG, now=now)
        second = create_refresh_token(USER_ID, CONFIG, now=now)
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            decode_token(first, "refresh", CONFIG).token_id,
            decode_token(second, "refresh", CONFIG).token_id,
        )

    def test_access_token_is_not_accepted_as_refresh(self) -> None:
        with self.assertRaises(InvalidTokenError):
            decode_token(create_access_token(USER_ID, CONFIG), "refresh", CONFIG)

    def test_refresh_token_is_not_accepted_as_access(self) -> None:
        with self.assertRaises(InvalidTokenError):
            decode_token(create_refresh_token(USER_ID, CONFIG), "access", CONFIG)

    def test_type_claim_is_checked_even_with_matching_secret(self) -> None:
        shared = replace(CONFIG, refresh_secret=ACCESS_SECRET)
        with self.assertRaisesRegex(InvalidTokenError, "type"):
            decode_token(create_access_token(USER_ID, shared), "refresh", shared)

    def test_expired_token_raises_expired_error(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=16)
        token = create_access_token(USER_ID, CONFIG, now=past)
        with self.assertRaises(TokenExpiredError):
            decode_token(token, "access", CONFIG)

    def test_expired_error_is_an_invalid_token_error(self) -> None:
        # Callers that only care "is it usable?" can catch one exception.
        self.assertTrue(issubclass(TokenExpiredError, InvalidTokenError))

    def test_token_signed_with_other_secret_is_rejected(self) -> None:
        other = replace(CONFIG, access_secret="x" * 32)
        with self.assertRaises(InvalidTokenError):
            decode_token(create_access_token(USER_ID, other), "access", CONFIG)

    def test_tampered_token_is_rejected(self) -> None:
        header, payload, signature = create_access_token(USER_ID, CONFIG).split(".")
        flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaises(InvalidTokenError):
            decode_token(f"{header}.{payload}.{flipped}", "access", CONFIG)

    def test_garbage_is_rejected(self) -> None:
        for token in ("", "not-a-jwt", "a.b.c"):
            with self.subTest(token=token), self.assertRaises(InvalidTokenError):
                decode_token(token, "access", CONFIG)

    def test_unsigned_none_algorithm_is_rejected(self) -> None:
        token = pyjwt.encode(_claims(), key=None, algorithm="none")
        with self.assertRaises(InvalidTokenError):
            decode_token(token, "access", CONFIG)

    def test_other_hmac_algorithm_is_rejected(self) -> None:
        # Only the configured algorithm is trusted, never the token's header.
        token = pyjwt.encode(_claims(), ACCESS_SECRET * 2, algorithm="HS512")
        with self.assertRaises(InvalidTokenError):
            decode_token(token, "access", CONFIG)

    def test_missing_claim_is_rejected(self) -> None:
        for claim in ("sub", "exp", "iat", "jti", "type"):
            claims = _claims()
            del claims[claim]
            token = pyjwt.encode(claims, ACCESS_SECRET, algorithm="HS256")
            with self.subTest(claim=claim), self.assertRaises(InvalidTokenError):
                decode_token(token, "access", CONFIG)

    def test_non_uuid_subject_is_rejected(self) -> None:
        token = pyjwt.encode(_claims(sub="admin"), ACCESS_SECRET, algorithm="HS256")
        with self.assertRaisesRegex(InvalidTokenError, "subject"):
            decode_token(token, "access", CONFIG)


def _claims(**overrides: object) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(USER_ID),
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    claims.update(overrides)
    return claims

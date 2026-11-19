import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from src.config import load_env

# RFC 7518 3.2: an HMAC key must be at least as long as the hash output.
MIN_SECRET_LENGTH = {"HS256": 32, "HS384": 48, "HS512": 64}
REQUIRED_CLAIMS = ["sub", "type", "jti", "iat", "exp"]

TokenType = Literal["access", "refresh"]


class InvalidTokenError(Exception):
    pass


class TokenExpiredError(InvalidTokenError):
    pass


@dataclass(frozen=True)
class JWTConfig:
    """Token secrets and lifetimes; defaults follow research.md section 8."""

    access_secret: str
    refresh_secret: str
    algorithm: str = "HS256"
    access_token_expire: timedelta = timedelta(minutes=15)
    refresh_token_expire: timedelta = timedelta(days=7)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "JWTConfig":
        env = load_env(env)

        algorithm = env.get("JWT_ALGORITHM", cls.algorithm)
        if algorithm not in MIN_SECRET_LENGTH:
            raise ValueError(
                f"JWT_ALGORITHM must be one of {', '.join(MIN_SECRET_LENGTH)}, "
                f"got {algorithm!r}"
            )

        min_length = MIN_SECRET_LENGTH[algorithm]
        access_secret = _secret(env, "JWT_SECRET_KEY", min_length)
        refresh_secret = _secret(env, "JWT_REFRESH_SECRET", min_length)
        if access_secret == refresh_secret:
            raise ValueError("JWT_SECRET_KEY and JWT_REFRESH_SECRET must be different")

        return cls(
            access_secret=access_secret,
            refresh_secret=refresh_secret,
            algorithm=algorithm,
            access_token_expire=timedelta(
                minutes=_positive_int(env, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)
            ),
            refresh_token_expire=timedelta(
                days=_positive_int(env, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
            ),
        )

    def secret_for(self, token_type: TokenType) -> str:
        return {"access": self.access_secret, "refresh": self.refresh_secret}[
            token_type
        ]

    def lifetime_for(self, token_type: TokenType) -> timedelta:
        return {
            "access": self.access_token_expire,
            "refresh": self.refresh_token_expire,
        }[token_type]


def _secret(env: Mapping[str, str], key: str, min_length: int) -> str:
    secret = env.get(key)
    if not secret:
        raise RuntimeError(f"{key} is not set. Generate one with: openssl rand -hex 32")
    if secret.startswith("change-me"):
        raise ValueError(
            f"{key} still has the .env.example placeholder. "
            "Generate one with: openssl rand -hex 32"
        )
    if len(secret) < min_length:
        raise ValueError(
            f"{key} must be at least {min_length} characters. "
            "Generate one with: openssl rand -hex 32"
        )
    return secret


def _positive_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{key} must be greater than 0, got {raw!r}")
    return value


@dataclass(frozen=True)
class TokenPayload:
    subject: uuid.UUID
    token_type: TokenType
    token_id: str
    issued_at: datetime
    expires_at: datetime


def create_access_token(
    user_id: uuid.UUID, config: JWTConfig, now: datetime | None = None
) -> str:
    return _create_token(user_id, "access", config, now)


def create_refresh_token(
    user_id: uuid.UUID, config: JWTConfig, now: datetime | None = None
) -> str:
    return _create_token(user_id, "refresh", config, now)


def _create_token(
    user_id: uuid.UUID,
    token_type: TokenType,
    config: JWTConfig,
    now: datetime | None,
) -> str:
    issued_at = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "type": token_type,
        # Random id keeps tokens unique even when issued in the same second.
        "jti": uuid.uuid4().hex,
        "iat": issued_at,
        "exp": issued_at + config.lifetime_for(token_type),
    }
    return jwt.encode(claims, config.secret_for(token_type), config.algorithm)


def decode_token(
    token: str, expected_type: TokenType, config: JWTConfig
) -> TokenPayload:
    """Verifies signature, expiry and token type, then returns the claims."""
    try:
        claims = jwt.decode(
            token,
            config.secret_for(expected_type),
            # Pin the algorithm so the token header can never choose it ("none").
            algorithms=[config.algorithm],
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as error:
        raise TokenExpiredError("Token has expired") from error
    except jwt.InvalidTokenError as error:
        raise InvalidTokenError(f"Invalid token: {error}") from error

    if claims["type"] != expected_type:
        raise InvalidTokenError(f"Expected {expected_type} token type")
    try:
        subject = uuid.UUID(claims["sub"])
    except ValueError:
        raise InvalidTokenError("Token subject is not a user id") from None

    return TokenPayload(
        subject=subject,
        token_type=expected_type,
        token_id=claims["jti"],
        issued_at=datetime.fromtimestamp(claims["iat"], UTC),
        expires_at=datetime.fromtimestamp(claims["exp"], UTC),
    )

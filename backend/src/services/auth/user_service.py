import asyncio
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.error_messages import ERROR_MESSAGES, SIGNUP_MESSAGES
from src.api.exceptions import AppError, ConflictError, FieldValidationError
from src.models import RefreshToken, User
from src.utils.security import (
    BCRYPT_MAX_PASSWORD_BYTES,
    hash_password,
    hash_token,
    verify_password,
)

logger = logging.getLogger(__name__)

# Narrower than the database's valid_email check, whose [A-Z|a-z] also lets "|"
# through in the domain ending.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_MAX_LENGTH = 255
PASSWORD_MIN_LENGTH = 8


class EmailTakenError(ConflictError):
    error = "email_taken"
    message = ERROR_MESSAGES["email_taken"]


class InvalidCredentialsError(AppError):
    """Same error for a wrong password and an unknown email, on purpose."""

    status_code = 401
    error = "invalid_credentials"
    message = ERROR_MESSAGES["invalid_credentials"]


def normalize_email(email: str) -> str:
    # Email uniqueness in the database is case-sensitive; one form prevents
    # A@x.com and a@x.com from becoming two accounts.
    return email.strip().lower()


def mask_email(email: str) -> str:
    """Log-safe form: requirements-addendum says u***@example.com."""
    local, at_sign, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if at_sign else "***"


def _check_email(email: str) -> None:
    if len(email) > EMAIL_MAX_LENGTH or not EMAIL_PATTERN.fullmatch(email):
        raise FieldValidationError("email", SIGNUP_MESSAGES["invalid_email"])


def _check_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise FieldValidationError("password", SIGNUP_MESSAGES["too_short"])
    if len(password.encode()) > BCRYPT_MAX_PASSWORD_BYTES:
        raise FieldValidationError("password", SIGNUP_MESSAGES["too_long"])
    has_letter = any(character.isalpha() for character in password)
    has_digit = any(character.isdigit() for character in password)
    if not (has_letter and has_digit):
        raise FieldValidationError("password", SIGNUP_MESSAGES["needs_mix"])


@cache
def _unmatchable_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


class UserService:
    """Account rules. Issuing tokens belongs to TokenService (T026).

    bcrypt takes about 0.2 seconds of CPU, so it runs in a worker thread;
    on the event loop it would stall every other request meanwhile.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, email: str, password: str) -> User:
        email = normalize_email(email)
        _check_email(email)
        _check_password(password)

        password_hash = await asyncio.to_thread(hash_password, password)
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        try:
            # Rely on the UNIQUE constraint: checking first would let two
            # simultaneous sign-ups both pass the check.
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            logger.warning("register_rejected email=%s", mask_email(email))
            raise EmailTakenError() from None
        logger.info("user_registered user_id=%s", user.id)
        return user

    async def login(self, email: str, password: str) -> User:
        email = normalize_email(email)
        user = await self.session.scalar(select(User).where(User.email == email))
        # An unknown email still costs one bcrypt check, otherwise the faster
        # answer would reveal which emails have accounts.
        stored_hash = (
            user.password_hash if user else await asyncio.to_thread(_unmatchable_hash)
        )
        matches = await asyncio.to_thread(verify_password, password, stored_hash)
        if user is None or not matches:
            logger.warning("login_failed email=%s", mask_email(email))
            raise InvalidCredentialsError()

        user.last_login_at = datetime.now(UTC)
        await self.session.commit()
        logger.info("login_succeeded user_id=%s", user.id)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def logout(self, refresh_token: str) -> None:
        """Revokes this session only; other devices stay signed in.

        Unknown or already revoked tokens are ignored, so logging out is
        always safe to repeat.
        """
        token = await self.session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.revoked.is_(False),
            )
        )
        if token is None:
            return
        token.revoke()
        await self.session.commit()
        logger.info("logout user_id=%s", token.user_id)

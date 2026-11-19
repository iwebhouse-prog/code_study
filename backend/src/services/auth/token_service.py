import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.error_messages import ERROR_MESSAGES
from src.api.exceptions import AppError
from src.models import RefreshToken
from src.utils.jwt import (
    InvalidTokenError,
    JWTConfig,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from src.utils.security import hash_token

logger = logging.getLogger(__name__)


class SessionExpiredError(AppError):
    """The session cannot continue; the user has to sign in again."""

    status_code = 401
    error = "session_expired"
    message = ERROR_MESSAGES["session_expired"]


class AccessTokenExpiredError(AppError):
    """Routine after 15 minutes; the frontend answers with a refresh."""

    status_code = 401
    error = "token_expired"
    message = ERROR_MESSAGES["token_expired"]


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class TokenService:
    """Issues, checks and rotates JWT pairs (research.md section 8)."""

    def __init__(self, session: AsyncSession, config: JWTConfig) -> None:
        self.session = session
        self.config = config

    async def issue_tokens(
        self, user_id: uuid.UUID, now: datetime | None = None
    ) -> TokenPair:
        pair = self._add_session(user_id, now or datetime.now(UTC))
        await self.session.commit()
        return pair

    def verify_access_token(self, token: str) -> uuid.UUID:
        try:
            return decode_token(token, "access", self.config).subject
        except TokenExpiredError:
            raise AccessTokenExpiredError() from None
        except InvalidTokenError:
            raise SessionExpiredError() from None

    async def rotate(self, refresh_token: str) -> TokenPair:
        """Swaps a refresh token for a new pair; each token works only once."""
        try:
            decode_token(refresh_token, "refresh", self.config)
        except InvalidTokenError as error:  # includes TokenExpiredError
            logger.warning("token_refresh_failed reason=%s", type(error).__name__)
            raise SessionExpiredError() from None

        # Lock the row so simultaneous requests with one token run in turn:
        # the second then sees it revoked instead of getting a pair of its own.
        stored = await self.session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(refresh_token))
            .with_for_update()
        )
        if stored is None:
            logger.warning("token_refresh_failed reason=not_stored")
            raise SessionExpiredError()

        if stored.revoked:
            # A used token arriving again means two parties hold it. We cannot
            # tell which is the thief, and refusing only this request would
            # leave a thief who rotated first signed in.
            logger.warning("token_reuse_detected user_id=%s", stored.user_id)
            await self.revoke_all(stored.user_id)
            raise SessionExpiredError()

        stored.revoke()
        pair = self._add_session(stored.user_id, datetime.now(UTC))
        await self.session.commit()
        logger.info("token_rotated user_id=%s", stored.user_id)
        return pair

    async def revoke_all(self, user_id: uuid.UUID) -> int:
        """Ends every session of a user; returns how many were still active."""
        result = await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )
        await self.session.commit()
        return cast(CursorResult[tuple[()]], result).rowcount

    def _add_session(self, user_id: uuid.UUID, now: datetime) -> TokenPair:
        refresh_token = create_refresh_token(user_id, self.config, now=now)
        self.session.add(
            RefreshToken(
                user_id=user_id,
                token_hash=hash_token(refresh_token),
                expires_at=now + self.config.refresh_token_expire,
            )
        )
        access_token = create_access_token(user_id, self.config, now=now)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

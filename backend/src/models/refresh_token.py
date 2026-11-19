import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    """One signed-in session; table created by migration 001 (data-model.md).

    Stores only the SHA-256 hash of the token. The table has no updated_at, so
    this model does not use TimestampMixin.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked: Mapped[bool] = mapped_column(server_default=text("false"))
    revoked_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(back_populates="refresh_tokens", lazy="raise")

    def revoke(self) -> None:
        """The one place that sets revoked and revoked_at, so they stay in step."""
        self.revoked = True
        self.revoked_at = datetime.now(UTC)

    def __repr__(self) -> str:
        # Explicit so token_hash can never reach a log line.
        return f"<RefreshToken id={self.id} user_id={self.user_id}>"

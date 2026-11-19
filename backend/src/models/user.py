from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.refresh_token import RefreshToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform account; table created by migration 001 (data-model.md)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            r"email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'",
            name="valid_email",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    skill_level: Mapped[str | None] = mapped_column(
        String(50), server_default=text("'Complete Beginner'")
    )
    last_login_at: Mapped[datetime | None]

    # lazy="raise": async sessions cannot lazy-load, so load this explicitly.
    # passive_deletes: the database's ON DELETE CASCADE removes the tokens.
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="user",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        # Explicit so password_hash can never reach a log line (data-model.md).
        return f"<User id={self.id} email={self.email!r}>"

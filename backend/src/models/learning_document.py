import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.task import Task

# The hard task limit (constitution V): a run still going after this is dead.
STALE_AFTER = timedelta(seconds=300)
CHAPTER_KEYS = tuple(f"chapter{number}" for number in range(1, 8))
_CONTENT_CHECK = "jsonb_typeof(content) = 'object' AND " + " AND ".join(
    f"content ? '{key}'" for key in CHAPTER_KEYS
)


class LearningDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The 7-chapter learning document for one task (data-model.md).

    Table created by migration 001. Generation moves pending -> in_progress ->
    completed or failed; a failed document may start again. Only the methods
    below change those fields, so they always agree. A completed document is
    final (FR-038: stored once, never regenerated on view).
    """

    __tablename__ = "learning_documents"

    STATUSES = ("pending", "in_progress", "completed", "failed")
    CHAPTER_KEYS = CHAPTER_KEYS

    __table_args__ = (
        CheckConstraint(_CONTENT_CHECK, name="valid_content_structure"),
        # Same name PostgreSQL gave the migration's unnamed column check.
        CheckConstraint(
            "generation_status IN ('pending', 'in_progress', 'completed', 'failed')",
            name="learning_documents_generation_status_check",
        ),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), unique=True
    )
    # Plain JSONB: changing the dict in place is not saved, which suits a
    # document that must not change once written.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generation_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'")
    )
    generation_started_at: Mapped[datetime | None]
    generation_completed_at: Mapped[datetime | None]
    generation_error: Mapped[str | None] = mapped_column(Text)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    task: Mapped["Task"] = relationship(
        back_populates="learning_document", lazy="raise"
    )

    @staticmethod
    def empty_content() -> dict[str, Any]:
        """Content for a document still waiting: every chapter key, no text."""
        return {key: {} for key in CHAPTER_KEYS}

    @property
    def is_completed(self) -> bool:
        return self.generation_status == "completed"

    def _require_status(self, action: str, *allowed: str) -> None:
        if self.generation_status not in allowed:
            raise ValueError(
                f"cannot {action} a document that is {self.generation_status}"
            )

    def start(self, celery_task_id: str, now: datetime | None = None) -> None:
        self._require_status("start", "pending", "failed")
        self.generation_status = "in_progress"
        self.celery_task_id = celery_task_id
        self.generation_started_at = now or datetime.now(UTC)
        self.generation_completed_at = None
        self.generation_error = None

    def complete(self, content: Mapping[str, Any], now: datetime | None = None) -> None:
        self._require_status("complete", "in_progress")
        missing = [key for key in CHAPTER_KEYS if key not in content]
        if missing:
            raise ValueError(f"content is missing {', '.join(missing)}")
        self.content = dict(content)
        self.generation_status = "completed"
        self.generation_completed_at = now or datetime.now(UTC)

    def is_stale(self, now: datetime | None = None) -> bool:
        """True for a run that outlived the Celery hard time limit (300 s)."""
        if self.generation_status != "in_progress" or not self.generation_started_at:
            return False
        return (now or datetime.now(UTC)) - self.generation_started_at > STALE_AFTER

    def can_restart(self, now: datetime | None = None) -> bool:
        return self.generation_status == "failed" or self.is_stale(now)

    def restart(self, now: datetime | None = None) -> None:
        """Failed (or stale) -> pending again, with the old run's traces cleared."""
        if not self.can_restart(now):
            raise ValueError(
                f"cannot restart a document that is {self.generation_status}"
            )
        self.generation_status = "pending"
        self.generation_error = None
        self.generation_started_at = None
        self.generation_completed_at = None
        self.celery_task_id = None

    def fail(self, error: str, now: datetime | None = None) -> None:
        self._require_status("fail", "in_progress")
        self.generation_status = "failed"
        self.generation_error = error
        self.generation_completed_at = now or datetime.now(UTC)

    @validates("content")
    def _keep_completed_content(
        self, _key: str, content: dict[str, Any]
    ) -> dict[str, Any]:
        if self.__dict__.get("generation_status") == "completed":
            raise ValueError("content of a completed document cannot change")
        return content

    def __repr__(self) -> str:
        return (
            f"<LearningDocument task_id={self.task_id} "
            f"status={self.generation_status}>"
        )

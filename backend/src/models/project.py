import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.task import Task
    from src.models.user import User


class Project(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A user's learning project; table created by migration 001 (data-model.md)."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("char_length(title) >= 1", name="title_min_length"),
        # Same name PostgreSQL gave the migration's unnamed column check.
        CheckConstraint(
            "deletion_status IN ('active', 'trashed')",
            name="projects_deletion_status_check",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    last_activity_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="projects", lazy="raise")
    # FR-003: tasks are listed in task-number order.
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Task.task_number",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} title={self.title!r}>"

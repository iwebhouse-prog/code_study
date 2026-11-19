import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Select,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.learning_document import LearningDocument
    from src.models.project import Project
    from src.models.uploaded_code import UploadedCode


class Task(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """One learning unit in a project; table created by migration 001 (data-model.md).

    Task numbers count up within a project and never change (FR-002, FR-004).
    """

    __tablename__ = "tasks"

    UPLOAD_METHODS = ("file", "folder", "paste")

    __table_args__ = (
        CheckConstraint("char_length(title) >= 5", name="title_min_length"),
        CheckConstraint(
            "char_length(description) <= 500", name="description_max_length"
        ),
        # Same names PostgreSQL gave the migration's unnamed column checks.
        CheckConstraint(
            "upload_method IN ('file', 'folder', 'paste')",
            name="tasks_upload_method_check",
        ),
        CheckConstraint(
            "deletion_status IN ('active', 'trashed')",
            name="tasks_deletion_status_check",
        ),
        UniqueConstraint(
            "project_id", "task_number", name="unique_task_number_per_project"
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    task_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    upload_method: Mapped[str | None] = mapped_column(String(20))

    project: Mapped["Project"] = relationship(back_populates="tasks", lazy="raise")
    uploaded_code: Mapped["UploadedCode | None"] = relationship(
        back_populates="task",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    learning_document: Mapped["LearningDocument | None"] = relationship(
        back_populates="task",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @classmethod
    def next_number_query(cls, project_id: uuid.UUID) -> Select[int]:
        """The number the project's next task gets: its highest number plus one.

        Trashed tasks count too, so a restored task never clashes with a newer
        one. Two concurrent creates can read the same value; the unique
        constraint rejects the second, and TaskService (T068) handles that.
        """
        return select(func.coalesce(func.max(cls.task_number), 0) + 1).where(
            cls.project_id == project_id
        )

    @validates("task_number")
    def _keep_number_fixed(self, _key: str, number: int) -> int:
        # FR-004/FR-005: once assigned, a task's number never changes.
        current = self.__dict__.get("task_number")
        if current is not None and current != number:
            raise ValueError(f"task_number is fixed at {current}; cannot set {number}")
        return number

    def __repr__(self) -> str:
        return f"<Task id={self.id} number={self.task_number} title={self.title!r}>"

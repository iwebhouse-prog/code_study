import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.code_file import CodeFile
    from src.models.task import Task


class UploadedCode(UUIDPrimaryKeyMixin, Base):
    """The code uploaded for one task, with its analysis summary.

    Table created by migration 001 (data-model.md). One per task; the files
    themselves are CodeFile rows (T063). Language and complexity may be empty
    until analysis (T065, T066) fills them in.
    """

    __tablename__ = "uploaded_code"
    # Uploads are never edited, so the table has created_at but no updated_at;
    # eager_defaults still lets created_at be read right after an insert.
    __mapper_args__ = {"eager_defaults": True}

    COMPLEXITY_LEVELS = ("beginner", "intermediate", "advanced")
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # FR-014

    __table_args__ = (
        CheckConstraint("upload_size_bytes <= 10485760", name="valid_upload_size"),
        # Same name PostgreSQL gave the migration's unnamed column check.
        CheckConstraint(
            "complexity_level IN ('beginner', 'intermediate', 'advanced')",
            name="uploaded_code_complexity_level_check",
        ),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), unique=True
    )
    detected_language: Mapped[str | None] = mapped_column(String(50))
    complexity_level: Mapped[str | None] = mapped_column(String(20))
    total_lines: Mapped[int | None] = mapped_column(Integer)
    total_files: Mapped[int | None] = mapped_column(Integer)
    upload_size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    task: Mapped["Task"] = relationship(back_populates="uploaded_code", lazy="raise")
    # Folder uploads read like a file tree: by relative path, then by name.
    files: Mapped[list["CodeFile"]] = relationship(
        back_populates="uploaded_code",
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(CodeFile.file_path, CodeFile.file_name)",
    )

    def __repr__(self) -> str:
        return (
            f"<UploadedCode id={self.id} language={self.detected_language!r} "
            f"bytes={self.upload_size_bytes}>"
        )

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.models.uploaded_code import UploadedCode


class CodeFile(UUIDPrimaryKeyMixin, Base):
    """One file of an upload; table created by migration 001 (data-model.md).

    The content lives on disk at `storage_path` (T067); this row describes it.
    """

    __tablename__ = "code_files"
    # Files are never edited, so the table has created_at but no updated_at;
    # eager_defaults still lets created_at be read right after an insert.
    __mapper_args__ = {"eager_defaults": True}

    # FR-015. Lower case only: the database check compares exactly.
    SUPPORTED_EXTENSIONS = (
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".html",
        ".css",
        ".java",
        ".cpp",
        ".c",
        ".txt",
        ".md",
    )

    __table_args__ = (
        CheckConstraint(
            "file_extension IN ("
            + ", ".join(f"'{ext}'" for ext in SUPPORTED_EXTENSIONS)
            + ")",
            name="supported_extension",
        ),
    )

    uploaded_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploaded_code.id", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    # Relative path inside an uploaded folder, e.g. "src/app.js".
    file_path: Mapped[str | None] = mapped_column(Text)
    file_extension: Mapped[str | None] = mapped_column(String(20))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    uploaded_code: Mapped["UploadedCode"] = relationship(
        back_populates="files", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<CodeFile id={self.id} name={self.file_name!r} "
            f"bytes={self.file_size_bytes}>"
        )

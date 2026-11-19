"""Response shapes of the task endpoints (contracts/tasks-api.md)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from src.api.error_messages import TASK_MESSAGES
from src.models import CodeFile, Task
from src.services.code_analysis.language_detector import LANGUAGE_BY_EXTENSION


class CodeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    detected_language: str | None
    complexity_level: str | None
    total_lines: int | None
    total_files: int | None
    upload_size_bytes: int | None


class TaskResponse(BaseModel):
    """The Task object; never carries user_id, storage_path or trash fields."""

    id: uuid.UUID
    project_id: uuid.UUID
    task_number: int
    title: str
    description: str | None
    upload_method: str | None
    created_at: datetime
    updated_at: datetime
    code: CodeSummary | None


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    file_path: str | None
    file_extension: str | None
    file_size_bytes: int | None
    language: str


class UploadResponse(TaskResponse):
    files: list[FileResponse]
    excluded_paths: list[str]


class FileContentResponse(FileResponse):
    content: str


class CodeResponse(BaseModel):
    task_id: uuid.UUID
    detected_language: str | None
    files: list[FileContentResponse]


class TaskUpdate(BaseModel):
    """Fields left out stay as they are; `description: null` clears it."""

    title: str | None = None
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_is_not_null(cls, value: str | None) -> str:
        # A title cannot be cleared; only a left-out title means "no change".
        if value is None:
            raise ValueError(TASK_MESSAGES["title_too_short"])
        return value

    def changes(self) -> dict[str, Any]:
        """Only the fields the client sent, so the service can tell UNSET from None."""
        return self.model_dump(include=self.model_fields_set)


def task_fields(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "project_id": task.project_id,
        "task_number": task.task_number,
        "title": task.title,
        "description": task.description,
        "upload_method": task.upload_method,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "code": (
            CodeSummary.model_validate(task.uploaded_code)
            if task.uploaded_code
            else None
        ),
    }


def file_fields(file: CodeFile) -> dict[str, Any]:
    return {
        "id": file.id,
        "file_name": file.file_name,
        "file_path": file.file_path,
        "file_extension": file.file_extension,
        "file_size_bytes": file.file_size_bytes,
        # Named by the extension; the content-based guess is only for the whole
        # upload's detected_language.
        "language": LANGUAGE_BY_EXTENSION.get(file.file_extension or "", "text"),
    }


def files_of(task: Task) -> list[CodeFile]:
    """The task's uploaded files; none for a task created without code."""
    return task.uploaded_code.files if task.uploaded_code else []

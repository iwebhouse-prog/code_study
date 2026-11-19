"""Task endpoints (T070-T075); the contract is contracts/tasks-api.md."""

import asyncio
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from starlette.datastructures import FormData, UploadFile

from src.api.dependencies import (
    CodeUploadServiceDep,
    CurrentUser,
    FileStorageDep,
    TaskServiceDep,
)
from src.api.exceptions import ErrorResponse
from src.api.task_schemas import (
    CodeResponse,
    FileContentResponse,
    FileResponse,
    TaskResponse,
    TaskUpdate,
    UploadResponse,
    file_fields,
    files_of,
    task_fields,
)
from src.models import Task, UploadedCode
from src.services.code_analysis.upload_files import IncomingFile, PastedCode
from src.services.task_service import TaskDraft

router = APIRouter()

# A pasted program may be as large as a whole upload (FR-014), plus a little
# slack so an oversized one reaches file_too_large instead of a form error.
MAX_FORM_PART_BYTES = UploadedCode.MAX_UPLOAD_BYTES + 1024

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "not signed in"},
}
_TASK_ERRORS: dict[int | str, dict[str, Any]] = {
    **_AUTH_ERRORS,
    400: {"model": ErrorResponse, "description": "validation_error"},
    403: {"model": ErrorResponse, "description": "forbidden"},
    404: {"model": ErrorResponse, "description": "not_found"},
}
_UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    **_TASK_ERRORS,
    400: {
        "model": ErrorResponse,
        "description": (
            "validation_error, no_files, too_many_files, unsupported_file_type, "
            "binary_file, unsupported_encoding or invalid_file_path"
        ),
    },
    413: {"model": ErrorResponse, "description": "file_too_large"},
}


@router.get(
    "/projects/{project_id}/tasks",
    summary="List a project's tasks by task number",
    responses=_TASK_ERRORS,
)
async def list_tasks(
    project_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep
) -> list[TaskResponse]:
    tasks = await service.list_for_user(project_id, user.id)
    return [TaskResponse(**task_fields(task)) for task in tasks]


@dataclass(frozen=True)
class UploadInput:
    draft: TaskDraft
    source: list[IncomingFile] | PastedCode


def _text(form: FormData, name: str) -> str | None:
    value = form.get(name)
    # A file sent under a text field's name is not text.
    return value if isinstance(value, str) else None


async def read_upload_form(request: Request) -> UploadInput:
    """Reads the multipart form by hand.

    Starlette limits a text field to 1MB by default, which would reject a large
    pasted program with a generic 400; the limit is raised to the upload limit
    so the contract's file_too_large (413) applies instead.
    """
    form = await request.form(max_part_size=MAX_FORM_PART_BYTES)
    draft = TaskDraft(
        _text(form, "title") or "",
        _text(form, "description"),
        _text(form, "upload_method") or "",
    )
    if draft.upload_method == "paste":
        source: list[IncomingFile] | PastedCode = PastedCode(
            _text(form, "code") or "", _text(form, "language")
        )
    else:
        parts = [part for part in form.getlist("files") if isinstance(part, UploadFile)]
        source = [
            IncomingFile(part.filename or "", await part.read()) for part in parts
        ]
    return UploadInput(draft, source)


UploadInputDep = Annotated[UploadInput, Depends(read_upload_form)]

_UPLOAD_FORM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "upload_method"],
    "properties": {
        "title": {"type": "string", "minLength": 5, "maxLength": 255},
        "description": {"type": "string", "maxLength": 500},
        "upload_method": {"type": "string", "enum": list(Task.UPLOAD_METHODS)},
        "files": {
            "type": "array",
            "items": {"type": "string", "format": "binary"},
            "description": "file/folder: one part per file; folders use the "
            "relative path as the part's filename",
        },
        "code": {"type": "string", "description": "paste: the pasted text"},
        "language": {"type": "string", "description": "paste: required language"},
    },
}


@router.post(
    "/projects/{project_id}/tasks",
    status_code=201,
    summary="Create a task and upload its code (multipart/form-data)",
    responses=_UPLOAD_ERRORS,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"multipart/form-data": {"schema": _UPLOAD_FORM_SCHEMA}},
        }
    },
)
async def create_task(
    project_id: uuid.UUID,
    user: CurrentUser,
    service: CodeUploadServiceDep,
    upload: UploadInputDep,
) -> UploadResponse:
    result = await service.create_task_with_code(
        project_id, user.id, upload.draft, upload.source
    )
    task = result.task
    return UploadResponse(
        **task_fields(task),
        files=[FileResponse(**file_fields(f)) for f in files_of(task)],
        excluded_paths=result.excluded_paths,
    )


@router.get("/tasks/{task_id}", summary="One task", responses=_TASK_ERRORS)
async def get_task(
    task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep
) -> TaskResponse:
    task = await service.get_for_user(task_id, user.id)
    return TaskResponse(**task_fields(task))


@router.patch(
    "/tasks/{task_id}",
    summary="Change title and/or description",
    responses=_TASK_ERRORS,
)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, user: CurrentUser, service: TaskServiceDep
) -> TaskResponse:
    task = await service.update_for_user(task_id, user.id, **body.changes())
    return TaskResponse(**task_fields(task))


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Move a task to the trash",
    responses=_TASK_ERRORS,
)
async def delete_task(
    task_id: uuid.UUID, user: CurrentUser, service: TaskServiceDep
) -> None:
    await service.move_to_trash_for_user(task_id, user.id)


@router.get(
    "/tasks/{task_id}/code",
    summary="The task's uploaded files with their content",
    responses={
        **_TASK_ERRORS,
        404: {"model": ErrorResponse, "description": "not_found or file_missing"},
    },
)
async def get_task_code(
    task_id: uuid.UUID,
    user: CurrentUser,
    service: TaskServiceDep,
    storage: FileStorageDep,
) -> CodeResponse:
    task = await service.get_with_files_for_user(task_id, user.id)
    files = []
    for row in files_of(task):
        content = await asyncio.to_thread(storage.read, row.storage_path)
        files.append(FileContentResponse(**file_fields(row), content=content))
    return CodeResponse(
        task_id=task.id,
        detected_language=(
            task.uploaded_code.detected_language if task.uploaded_code else None
        ),
        files=files,
    )

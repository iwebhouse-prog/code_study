"""Learning document endpoints (T097, T098); contract: contracts/documents-api.md.

Ownership works as for tasks: TaskService answers 403/404 before any document
is looked at. Responses never carry the stored error detail, storage paths or
Celery ids.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, DocumentQueueServiceDep, TaskServiceDep
from src.api.error_messages import DOCUMENT_MESSAGES
from src.api.exceptions import ErrorResponse
from src.services.document.document_queue_service import DocumentStatus

router = APIRouter()

_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "validation_error"},
    401: {"model": ErrorResponse, "description": "not signed in"},
    403: {"model": ErrorResponse, "description": "forbidden"},
    404: {
        "model": ErrorResponse,
        "description": "not_found (task) or document_not_found",
    },
}


class DocumentError(BaseModel):
    reason: str
    message: str


class DocumentStatusResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    estimated_seconds_remaining: int | None
    error: DocumentError | None


class DocumentResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    completed_at: datetime | None
    content: dict[str, Any]


def status_response(status: DocumentStatus) -> DocumentStatusResponse:
    reason = status.error_reason
    return DocumentStatusResponse(
        task_id=status.task_id,
        status=status.status,
        started_at=status.started_at,
        completed_at=status.completed_at,
        estimated_seconds_remaining=status.estimated_seconds_remaining,
        error=(
            DocumentError(reason=reason, message=DOCUMENT_MESSAGES[reason])
            if reason
            else None
        ),
    )


@router.get(
    "/tasks/{task_id}/document",
    summary="The finished learning document",
    responses={
        **_ERRORS,
        409: {"model": ErrorResponse, "description": "document_not_ready"},
    },
)
async def get_document(
    task_id: uuid.UUID,
    user: CurrentUser,
    tasks: TaskServiceDep,
    queue: DocumentQueueServiceDep,
) -> DocumentResponse:
    await tasks.get_for_user(task_id, user.id)
    document = await queue.get_completed(task_id)
    return DocumentResponse(
        task_id=task_id,
        status=document.generation_status,
        completed_at=document.generation_completed_at,
        content=document.content,
    )


@router.get(
    "/tasks/{task_id}/document/status",
    summary="Generation progress of the learning document",
    responses=_ERRORS,
)
async def get_document_status(
    task_id: uuid.UUID,
    user: CurrentUser,
    tasks: TaskServiceDep,
    queue: DocumentQueueServiceDep,
) -> DocumentStatusResponse:
    await tasks.get_for_user(task_id, user.id)
    return status_response(await queue.status(task_id))


@router.post(
    "/tasks/{task_id}/document/regenerate",
    status_code=202,
    summary="Try again after a failed generation",
    responses={
        **_ERRORS,
        409: {"model": ErrorResponse, "description": "document_not_failed"},
    },
)
async def regenerate_document(
    task_id: uuid.UUID,
    user: CurrentUser,
    tasks: TaskServiceDep,
    queue: DocumentQueueServiceDep,
) -> DocumentStatusResponse:
    await tasks.get_for_user(task_id, user.id)
    return status_response(await queue.regenerate(task_id))

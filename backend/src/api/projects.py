"""Project endpoints (T046-T050); the contract is contracts/projects-api.md."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, field_validator

from src.api.dependencies import CurrentUser, ProjectServiceDep
from src.api.error_messages import PROJECT_MESSAGES
from src.api.exceptions import ErrorResponse
from src.models import Project
from src.services.project_service import ProjectService

router = APIRouter()

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "not signed in"},
}
_PROJECT_ERRORS: dict[int | str, dict[str, Any]] = {
    **_AUTH_ERRORS,
    400: {"model": ErrorResponse, "description": "validation_error"},
    403: {"model": ErrorResponse, "description": "forbidden"},
    404: {"model": ErrorResponse, "description": "not_found"},
}


class ProjectResponse(BaseModel):
    """The Project object of the contract; never carries user_id or trash fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    # Tasks outside the trash; filled in by _respond. Completed tasks are
    # counted once progress tracking exists (US4), so that stays 0.
    task_count: int = 0
    completed_task_count: int = 0


class ProjectCreate(BaseModel):
    title: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Fields left out stay as they are; `description: null` clears it."""

    title: str | None = None
    description: str | None = None

    @field_validator("title")
    @classmethod
    def title_is_not_null(cls, value: str | None) -> str:
        # A title cannot be cleared; only a left-out title means "no change".
        if value is None:
            raise ValueError(PROJECT_MESSAGES["title_required"])
        return value

    def changes(self) -> dict[str, Any]:
        """Only the fields the client sent, so the service can tell UNSET from None."""
        return self.model_dump(include=self.model_fields_set)


async def _respond(
    service: ProjectService, projects: list[Project]
) -> list[ProjectResponse]:
    counts = await service.task_counts(project.id for project in projects)
    return [
        ProjectResponse.model_validate(project).model_copy(
            update={"task_count": counts[project.id]}
        )
        for project in projects
    ]


@router.get(
    "",
    summary="List my projects, most recent activity first",
    responses=_AUTH_ERRORS,
)
async def list_projects(
    user: CurrentUser, service: ProjectServiceDep
) -> list[ProjectResponse]:
    return await _respond(service, await service.list_active(user.id))


@router.post(
    "",
    status_code=201,
    summary="Create a project",
    responses={**_AUTH_ERRORS, 400: _PROJECT_ERRORS[400]},
)
async def create_project(
    body: ProjectCreate, user: CurrentUser, service: ProjectServiceDep
) -> ProjectResponse:
    project = await service.create(user.id, body.title, body.description)
    return (await _respond(service, [project]))[0]


@router.get("/{project_id}", summary="One project", responses=_PROJECT_ERRORS)
async def get_project(
    project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep
) -> ProjectResponse:
    project = await service.get_for_user(project_id, user.id)
    return (await _respond(service, [project]))[0]


@router.patch(
    "/{project_id}",
    summary="Change title and/or description",
    responses=_PROJECT_ERRORS,
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    user: CurrentUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    project = await service.update_for_user(project_id, user.id, **body.changes())
    return (await _respond(service, [project]))[0]


@router.delete(
    "/{project_id}",
    status_code=204,
    summary="Move a project to the trash",
    responses=_PROJECT_ERRORS,
)
async def delete_project(
    project_id: uuid.UUID, user: CurrentUser, service: ProjectServiceDep
) -> None:
    await service.move_to_trash_for_user(project_id, user.id)

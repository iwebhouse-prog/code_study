import logging
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.error_messages import TASK_MESSAGES
from src.api.exceptions import FieldValidationError, ForbiddenError, NotFoundError
from src.models import Project, Task, UploadedCode
from src.services.project_service import UNSET, ProjectService, _Unset

logger = logging.getLogger(__name__)

__all__ = ["UNSET"]

TITLE_MIN_LENGTH = 5
TITLE_MAX_LENGTH = 255  # tasks.title is VARCHAR(255)
DESCRIPTION_MAX_LENGTH = 500


class TaskNotFoundError(NotFoundError):
    message = TASK_MESSAGES["not_found"]


class TaskForbiddenError(ForbiddenError):
    message = TASK_MESSAGES["forbidden"]


@dataclass(frozen=True)
class TaskDraft:
    """What a client sends to create a task (the code travels separately)."""

    title: str
    description: str | None
    upload_method: str


def clean_title(title: str) -> str:
    title = title.strip()
    if len(title) < TITLE_MIN_LENGTH:
        raise FieldValidationError("title", TASK_MESSAGES["title_too_short"])
    if len(title) > TITLE_MAX_LENGTH:
        raise FieldValidationError("title", TASK_MESSAGES["title_too_long"])
    return title


def clean_description(description: str | None) -> str | None:
    # A blank description means "no description", not an empty string.
    description = (description or "").strip()
    if len(description) > DESCRIPTION_MAX_LENGTH:
        raise FieldValidationError("description", TASK_MESSAGES["description_too_long"])
    return description or None


def clean_draft(draft: TaskDraft) -> TaskDraft:
    """A validated copy of the draft; the title is checked before the rest."""
    cleaned = replace(
        draft,
        title=clean_title(draft.title),
        description=clean_description(draft.description),
    )
    if cleaned.upload_method not in Task.UPLOAD_METHODS:
        raise FieldValidationError(
            "upload_method", TASK_MESSAGES["upload_method_invalid"]
        )
    return cleaned


class TaskService:
    """Task rules.

    API routes must use the *_for_user methods, which refuse tasks and projects
    of other users.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectService(session)

    async def create_for_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID, draft: TaskDraft
    ) -> Task:
        task = await self.add_for_user(project_id, user_id, draft)
        await self.session.commit()
        return task

    async def add_for_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID, draft: TaskDraft
    ) -> Task:
        """Adds the task without committing.

        The caller attaches the task's code and commits everything together
        (atomic upload).
        """
        project = await self.projects.get_for_user(project_id, user_id, lock=True)
        draft = clean_draft(draft)
        # The project row is locked, so no other create can read the same number.
        number = await self.session.scalar(Task.next_number_query(project_id))
        task = Task(
            project_id=project_id,
            task_number=number,
            title=draft.title,
            description=draft.description,
            upload_method=draft.upload_method,
            uploaded_code=None,
        )
        self.session.add(task)
        project.last_activity_at = datetime.now(UTC)
        await self.session.flush()
        return task

    async def list_for_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Task]:
        """The project's tasks outside the trash, task number ascending."""
        await self.projects.get_for_user(project_id, user_id)
        tasks = await self.session.scalars(
            select(Task)
            .options(selectinload(Task.uploaded_code))
            .where(Task.project_id == project_id, Task.deletion_status == "active")
            .order_by(Task.task_number)
        )
        return list(tasks.all())

    async def get_for_user(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task, _ = await self._load(task_id, user_id)
        return task

    async def get_with_files_for_user(
        self, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> Task:
        """Like get_for_user, with the code's file rows loaded too."""
        task, _ = await self._load(task_id, user_id, with_files=True)
        return task

    async def update_for_user(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        title: str | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
    ) -> Task:
        task, project = await self._load(task_id, user_id)
        # Both fields are checked before anything changes.
        new_title = task.title if isinstance(title, _Unset) else clean_title(title)
        new_description = (
            task.description
            if isinstance(description, _Unset)
            else clean_description(description)
        )
        task.title = new_title
        task.description = new_description
        project.last_activity_at = datetime.now(UTC)
        await self.session.commit()
        return task

    async def move_to_trash_for_user(
        self, task_id: uuid.UUID, user_id: uuid.UUID
    ) -> Task:
        task, project = await self._load(task_id, user_id)
        task.move_to_trash()
        project.last_activity_at = datetime.now(UTC)
        await self.session.commit()
        return task

    async def _load(
        self, task_id: uuid.UUID, user_id: uuid.UUID, *, with_files: bool = False
    ) -> tuple[Task, Project]:
        """An active task of an active project; other users' tasks give 403."""
        code = selectinload(Task.uploaded_code)
        row = (
            await self.session.execute(
                select(Task, Project)
                .options(code.selectinload(UploadedCode.files) if with_files else code)
                .join(Project, Task.project_id == Project.id)
                .where(
                    Task.id == task_id,
                    Task.deletion_status == "active",
                    Project.deletion_status == "active",
                )
            )
        ).first()
        if row is None:
            raise TaskNotFoundError()
        task, project = row
        if project.user_id != user_id:
            # requirements-addendum FR-110: log authorization failures.
            logger.warning("task_access_denied user_id=%s task_id=%s", user_id, task_id)
            raise TaskForbiddenError()
        return task, project

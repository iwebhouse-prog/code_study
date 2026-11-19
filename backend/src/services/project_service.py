import enum
import logging
import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.error_messages import PROJECT_MESSAGES
from src.api.exceptions import FieldValidationError, ForbiddenError, NotFoundError
from src.models import Project, Task

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 255  # projects.title is VARCHAR(255)


class ProjectNotFoundError(NotFoundError):
    message = PROJECT_MESSAGES["not_found"]


class ProjectForbiddenError(ForbiddenError):
    message = PROJECT_MESSAGES["forbidden"]


class _Unset(enum.Enum):
    """Marks "leave this field as it is", which differs from "clear it" (None)."""

    UNSET = enum.auto()


UNSET = _Unset.UNSET


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise FieldValidationError("title", PROJECT_MESSAGES["title_required"])
    if len(title) > TITLE_MAX_LENGTH:
        raise FieldValidationError("title", PROJECT_MESSAGES["title_too_long"])
    return title


def _clean_description(description: str | None) -> str | None:
    # A blank description means "no description", not an empty string.
    return (description or "").strip() or None


class ProjectService:
    """Project rules.

    API routes must use the *_for_user methods: they refuse other users'
    projects. get, update and move_to_trash skip that check and are for code
    that has already verified the owner.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user_id: uuid.UUID, title: str, description: str | None = None
    ) -> Project:
        project = Project(
            user_id=user_id,
            title=_clean_title(title),
            description=_clean_description(description),
        )
        self.session.add(project)
        await self.session.commit()
        return project

    async def list_active(self, user_id: uuid.UUID) -> list[Project]:
        """The user's projects outside the trash, most recently active first."""
        projects = await self.session.scalars(
            select(Project)
            .where(Project.user_id == user_id, Project.deletion_status == "active")
            .order_by(Project.last_activity_at.desc(), Project.created_at.desc())
        )
        return list(projects.all())

    async def task_counts(
        self, project_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        """How many tasks outside the trash each project has (0 when none)."""
        ids = list(project_ids)
        rows = await self.session.execute(
            select(Task.project_id, func.count())
            .where(Task.project_id.in_(ids), Task.deletion_status == "active")
            .group_by(Task.project_id)
        )
        counts = {project_id: count for project_id, count in rows}
        return {project_id: counts.get(project_id, 0) for project_id in ids}

    async def get(self, project_id: uuid.UUID, *, lock: bool = False) -> Project:
        """An active project; trashed ones count as missing outside the trash.

        lock=True holds the row (SELECT ... FOR UPDATE) until the transaction
        ends, so concurrent task creates in one project take turns.
        """
        query = select(Project).where(
            Project.id == project_id, Project.deletion_status == "active"
        )
        project = await self.session.scalar(query.with_for_update() if lock else query)
        if project is None:
            raise ProjectNotFoundError()
        return project

    async def update(
        self,
        project_id: uuid.UUID,
        *,
        title: str | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
    ) -> Project:
        project = await self.get(project_id)
        return await self._apply_update(project, title, description)

    async def move_to_trash(self, project_id: uuid.UUID) -> Project:
        return await self._trash(await self.get(project_id))

    async def get_for_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> Project:
        """Like get, but a project of another user is refused with 403."""
        project = await self.get(project_id, lock=lock)
        if project.user_id != user_id:
            # requirements-addendum FR-110: log authorization failures.
            logger.warning(
                "project_access_denied user_id=%s project_id=%s", user_id, project_id
            )
            raise ProjectForbiddenError()
        return project

    async def update_for_user(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        title: str | _Unset = UNSET,
        description: str | None | _Unset = UNSET,
    ) -> Project:
        project = await self.get_for_user(project_id, user_id)
        return await self._apply_update(project, title, description)

    async def move_to_trash_for_user(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> Project:
        return await self._trash(await self.get_for_user(project_id, user_id))

    async def _apply_update(
        self,
        project: Project,
        title: str | _Unset,
        description: str | None | _Unset,
    ) -> Project:
        # The title is checked first: a bad title fails before anything changes.
        if not isinstance(title, _Unset):
            project.title = _clean_title(title)
        if not isinstance(description, _Unset):
            project.description = _clean_description(description)
        await self.session.commit()
        return project

    async def _trash(self, project: Project) -> Project:
        # FR-009D also trashes the project's tasks; added with the Task model (T061).
        project.move_to_trash()
        await self.session.commit()
        return project

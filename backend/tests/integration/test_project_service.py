"""Runs ProjectService against PostgreSQL (T044)."""

import asyncio
import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from src.api.exceptions import FieldValidationError
from src.db.session import Database
from src.models import Project, User
from src.services.project_service import ProjectNotFoundError, ProjectService
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestProjectService(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self.database = Database(TEST_DATABASE_URL)
        self.user_id = await self._add_user("learner@example.com")

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add_user(self, email: str) -> uuid.UUID:
        async with self.database.session() as session:
            user = User(email=email, password_hash="hash")
            session.add(user)
            await session.commit()
            return user.id

    async def _create(
        self, title: str = "My Todo App", description: str | None = None
    ) -> Project:
        async with self.database.session() as session:
            return await ProjectService(session).create(
                self.user_id, title, description
            )

    async def _stored(self, project_id: uuid.UUID) -> Project:
        async with self.database.session() as session:
            project = await session.get(Project, project_id)
        assert project is not None
        return project

    async def test_create_saves_and_returns_the_project(self) -> None:
        project = await self._create("My Todo App", "할 일 앱 만들기")
        stored = await self._stored(project.id)
        self.assertEqual(stored.title, "My Todo App")
        self.assertEqual(stored.description, "할 일 앱 만들기")
        self.assertEqual(stored.user_id, self.user_id)
        self.assertEqual(stored.deletion_status, "active")
        self.assertIsNotNone(project.created_at)

    async def test_get_returns_an_active_project(self) -> None:
        created = await self._create()
        async with self.database.session() as session:
            found = await ProjectService(session).get(created.id)
        self.assertEqual(found.id, created.id)

    async def test_get_unknown_project_is_not_found(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(ProjectNotFoundError):
                await ProjectService(session).get(uuid.uuid4())

    async def test_list_shows_active_projects_most_recent_activity_first(self) -> None:
        old = await self._create("오래된 프로젝트")
        new = await self._create("최근 프로젝트")
        trashed = await self._create("버린 프로젝트")
        async with self.database.session() as session:
            # Explicit times: projects created in one test share nearly the same now().
            base = datetime(2026, 11, 1, tzinfo=UTC)
            for project, offset in ((old, 0), (new, 2), (trashed, 1)):
                await session.execute(
                    update(Project)
                    .where(Project.id == project.id)
                    .values(last_activity_at=base + timedelta(days=offset))
                )
            await session.commit()
            await ProjectService(session).move_to_trash(trashed.id)
        other_user = await self._add_user("other@example.com")
        async with self.database.session() as session:
            await ProjectService(session).create(other_user, "남의 프로젝트")
            projects = await ProjectService(session).list_active(self.user_id)
        self.assertEqual(
            [p.title for p in projects], ["최근 프로젝트", "오래된 프로젝트"]
        )

    async def test_list_of_a_user_without_projects_is_empty(self) -> None:
        async with self.database.session() as session:
            self.assertEqual(
                await ProjectService(session).list_active(self.user_id), []
            )

    async def test_update_changes_only_the_given_fields(self) -> None:
        created = await self._create("원래 제목", "원래 설명")
        async with self.database.session() as session:
            await ProjectService(session).update(created.id, title="  새 제목 ")
        stored = await self._stored(created.id)
        self.assertEqual(stored.title, "새 제목")
        self.assertEqual(stored.description, "원래 설명")

    async def test_update_can_clear_the_description(self) -> None:
        created = await self._create("제목", "지울 설명")
        async with self.database.session() as session:
            await ProjectService(session).update(created.id, description="  ")
        self.assertIsNone((await self._stored(created.id)).description)

    async def test_update_can_clear_the_description_with_none(self) -> None:
        created = await self._create("제목", "지울 설명")
        async with self.database.session() as session:
            await ProjectService(session).update(created.id, description=None)
        self.assertIsNone((await self._stored(created.id)).description)

    async def test_update_returns_fresh_values(self) -> None:
        created = await self._create()
        await asyncio.sleep(0.01)
        async with self.database.session() as session:
            updated = await ProjectService(session).update(
                created.id, title="바뀐 제목"
            )
        self.assertEqual(updated.title, "바뀐 제목")
        self.assertGreater(updated.updated_at, created.updated_at)

    async def test_update_rejects_an_empty_title_and_keeps_the_old_one(self) -> None:
        created = await self._create("원래 제목")
        async with self.database.session() as session:
            with self.assertRaises(FieldValidationError):
                await ProjectService(session).update(created.id, title=" ")
        self.assertEqual((await self._stored(created.id)).title, "원래 제목")

    async def test_move_to_trash_hides_the_project(self) -> None:
        created = await self._create()
        async with self.database.session() as session:
            await ProjectService(session).move_to_trash(created.id)
        stored = await self._stored(created.id)
        self.assertTrue(stored.is_trashed)
        self.assertIsNotNone(stored.scheduled_deletion_at)
        async with self.database.session() as session:
            with self.assertRaises(ProjectNotFoundError):
                await ProjectService(session).get(created.id)

    async def test_trashed_project_cannot_be_updated_or_trashed_again(self) -> None:
        created = await self._create()
        async with self.database.session() as session:
            await ProjectService(session).move_to_trash(created.id)
        async with self.database.session() as session:
            service = ProjectService(session)
            with self.assertRaises(ProjectNotFoundError):
                await service.update(created.id, title="새 제목")
            with self.assertRaises(ProjectNotFoundError):
                await service.move_to_trash(created.id)

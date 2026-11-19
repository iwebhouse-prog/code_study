"""Checks that only the owner can read or change a project (T045)."""

import unittest
import uuid

from sqlalchemy import select

from src.db.session import Database
from src.models import Project, User
from src.services.project_service import (
    ProjectForbiddenError,
    ProjectNotFoundError,
    ProjectService,
)
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

LOGGER = "src.services.project_service"


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestProjectOwnership(unittest.IsolatedAsyncioTestCase):
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
        self.owner = await self._add_user("owner@example.com")
        self.stranger = await self._add_user("stranger@example.com")
        async with self.database.session() as session:
            project = await ProjectService(session).create(
                self.owner, "내 프로젝트", "원래 설명"
            )
        self.project_id = project.id

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

    async def _stored(self) -> Project:
        async with self.database.session() as session:
            project = await session.get(Project, self.project_id)
        assert project is not None
        return project

    async def test_owner_can_read_update_and_trash(self) -> None:
        async with self.database.session() as session:
            service = ProjectService(session)
            found = await service.get_for_user(self.project_id, self.owner)
            self.assertEqual(found.title, "내 프로젝트")
            updated = await service.update_for_user(
                self.project_id, self.owner, title="새 제목", description=None
            )
            self.assertEqual((updated.title, updated.description), ("새 제목", None))
            await service.move_to_trash_for_user(self.project_id, self.owner)
        self.assertTrue((await self._stored()).is_trashed)

    async def test_update_for_user_changes_only_the_given_fields(self) -> None:
        async with self.database.session() as session:
            await ProjectService(session).update_for_user(
                self.project_id, self.owner, description="새 설명"
            )
        stored = await self._stored()
        self.assertEqual((stored.title, stored.description), ("내 프로젝트", "새 설명"))

    async def test_stranger_cannot_read(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(ProjectForbiddenError):
                await ProjectService(session).get_for_user(
                    self.project_id, self.stranger
                )

    async def test_stranger_cannot_update_and_nothing_changes(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(ProjectForbiddenError):
                await ProjectService(session).update_for_user(
                    self.project_id, self.stranger, title="가로챈 제목"
                )
        self.assertEqual((await self._stored()).title, "내 프로젝트")

    async def test_stranger_cannot_trash_and_nothing_changes(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(ProjectForbiddenError):
                await ProjectService(session).move_to_trash_for_user(
                    self.project_id, self.stranger
                )
        self.assertFalse((await self._stored()).is_trashed)

    async def test_missing_project_is_404_for_everyone(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(ProjectNotFoundError):
                await ProjectService(session).get_for_user(uuid.uuid4(), self.owner)

    async def test_trashed_project_is_404_even_for_its_owner(self) -> None:
        async with self.database.session() as session:
            await ProjectService(session).move_to_trash(self.project_id)
        async with self.database.session() as session:
            with self.assertRaises(ProjectNotFoundError):
                await ProjectService(session).get_for_user(self.project_id, self.owner)

    async def test_refusals_are_logged_for_audit(self) -> None:
        # requirements-addendum FR-110: authorization failures are logged.
        with self.assertLogs(LOGGER, "WARNING") as logs:
            async with self.database.session() as session:
                with self.assertRaises(ProjectForbiddenError):
                    await ProjectService(session).get_for_user(
                        self.project_id, self.stranger
                    )
        output = "\n".join(logs.output)
        self.assertIn("project_access_denied", output)
        self.assertIn(str(self.stranger), output)
        self.assertIn(str(self.project_id), output)

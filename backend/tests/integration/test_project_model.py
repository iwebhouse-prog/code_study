"""Checks the Project model against the real migrated table (T043)."""

import asyncio
import unittest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models import Project, User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by their defaults.
STRICTER_IN_MODEL = ("created_at", "updated_at", "last_activity_at", "deletion_status")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestProjectMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(Project, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestProjectPersistence(unittest.IsolatedAsyncioTestCase):
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
        async with self.database.session() as session:
            self.user = User(email="learner@example.com", password_hash="hash")
            session.add(self.user)
            await session.commit()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(self, title: str = "Python 기초", **fields: object) -> Project:
        async with self.database.session() as session:
            project = Project(user_id=self.user.id, title=title, **fields)
            session.add(project)
            await session.commit()
            return project

    async def _get(self, project_id: object) -> Project:
        async with self.database.session() as session:
            project = await session.get(Project, project_id)
        assert project is not None
        return project

    async def test_database_defaults_are_available_after_insert(self) -> None:
        project = await self._add()
        self.assertIsNotNone(project.id)
        self.assertEqual(project.deletion_status, "active")
        self.assertIsNone(project.description)
        self.assertIsNone(project.trashed_at)
        for value in (project.created_at, project.updated_at, project.last_activity_at):
            self.assertIsNotNone(value)

    async def test_korean_title_and_long_description_are_stored(self) -> None:
        project = await self._add("파이썬 기초 다지기", description="설명 " * 300)
        stored = await self._get(project.id)
        self.assertEqual(stored.title, "파이썬 기초 다지기")
        self.assertEqual(stored.description, "설명 " * 300)

    async def test_empty_title_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "title_min_length"):
            await self._add("")

    async def test_unknown_deletion_status_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            await self._add(deletion_status="deleted")

    async def test_trash_and_restore_are_saved(self) -> None:
        saved = await self._add()
        async with self.database.session() as session:
            project = await session.get(Project, saved.id)
            assert project is not None
            project.move_to_trash()
            await session.commit()
        trashed = await self._get(saved.id)
        self.assertTrue(trashed.is_trashed)
        assert trashed.trashed_at is not None and trashed.scheduled_deletion_at
        self.assertEqual((trashed.scheduled_deletion_at - trashed.trashed_at).days, 30)
        async with self.database.session() as session:
            project = await session.get(Project, saved.id)
            assert project is not None
            project.restore()
            await session.commit()
        self.assertFalse((await self._get(saved.id)).is_trashed)

    async def test_updated_at_is_readable_right_after_update(self) -> None:
        saved = await self._add()
        await asyncio.sleep(0.01)
        async with self.database.session() as session:
            project = await session.get(Project, saved.id)
            assert project is not None
            project.title = "새 제목"
            await session.commit()
            self.assertGreater(project.updated_at, saved.updated_at)

    async def test_user_lists_their_projects(self) -> None:
        await self._add("하나")
        await self._add("둘")
        async with self.database.session() as session:
            user = await session.scalar(
                select(User).options(selectinload(User.projects))
            )
        assert user is not None
        self.assertEqual({p.title for p in user.projects}, {"하나", "둘"})

    async def test_deleting_a_user_deletes_their_projects(self) -> None:
        await self._add()
        async with self.database.session() as session:
            await session.delete(await session.get(User, self.user.id))
            await session.commit()
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(Project))).all(), [])

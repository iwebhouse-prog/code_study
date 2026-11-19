"""Checks the Task model against the real migrated table (T061)."""

import unittest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models import Project, Task, User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by their defaults.
STRICTER_IN_MODEL = ("created_at", "updated_at", "deletion_status")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestTaskMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(Task, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestTaskPersistence(unittest.IsolatedAsyncioTestCase):
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
            await session.flush()
            self.project = Project(user_id=self.user.id, title="Todo 앱")
            self.other_project = Project(user_id=self.user.id, title="계산기")
            session.add_all([self.project, self.other_project])
            await session.commit()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(
        self,
        number: int,
        title: str = "할 일 추가 기능",
        project: Project | None = None,
        **fields: object,
    ) -> Task:
        async with self.database.session() as session:
            task = Task(
                project_id=(project or self.project).id,
                task_number=number,
                title=title,
                **fields,
            )
            session.add(task)
            await session.commit()
            return task

    async def _next_number(self, project: Project | None = None) -> int:
        async with self.database.session() as session:
            value = await session.scalar(
                Task.next_number_query((project or self.project).id)
            )
        assert value is not None
        return value

    async def test_database_defaults_are_available_after_insert(self) -> None:
        task = await self._add(1)
        self.assertIsNotNone(task.id)
        self.assertEqual(task.deletion_status, "active")
        self.assertIsNone(task.description)
        self.assertIsNone(task.upload_method)
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.updated_at)

    async def test_all_upload_methods_are_accepted(self) -> None:
        for number, method in enumerate(Task.UPLOAD_METHODS, start=1):
            task = await self._add(number, upload_method=method)
            self.assertEqual(task.upload_method, method)

    async def test_unknown_upload_method_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "upload_method"):
            await self._add(1, upload_method="zip")

    async def test_title_shorter_than_five_characters_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "title_min_length"):
            await self._add(1, title="로그인")

    async def test_five_character_korean_title_is_accepted(self) -> None:
        task = await self._add(1, title="로그인기능")
        self.assertEqual(task.title, "로그인기능")

    async def test_description_over_500_characters_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "description_max_length"):
            await self._add(1, description="가" * 501)

    async def test_description_of_500_characters_is_accepted(self) -> None:
        task = await self._add(1, description="가" * 500)
        self.assertEqual(len(task.description or ""), 500)

    async def test_duplicate_number_in_one_project_is_rejected(self) -> None:
        await self._add(1)
        with self.assertRaisesRegex(IntegrityError, "unique_task_number_per_project"):
            await self._add(1)

    async def test_each_project_numbers_its_own_tasks(self) -> None:
        await self._add(1)
        task = await self._add(1, project=self.other_project)
        self.assertEqual(task.task_number, 1)

    async def test_first_task_gets_number_one(self) -> None:
        self.assertEqual(await self._next_number(), 1)

    async def test_next_number_follows_the_highest(self) -> None:
        await self._add(1)
        await self._add(2)
        self.assertEqual(await self._next_number(), 3)
        self.assertEqual(await self._next_number(self.other_project), 1)

    async def test_trashed_task_numbers_are_not_reused(self) -> None:
        await self._add(1)
        await self._add(2, deletion_status="trashed")
        self.assertEqual(await self._next_number(), 3)

    async def test_trash_and_restore_are_saved(self) -> None:
        saved = await self._add(1)
        async with self.database.session() as session:
            task = await session.get(Task, saved.id)
            assert task is not None
            task.move_to_trash()
            await session.commit()
        async with self.database.session() as session:
            trashed = await session.get(Task, saved.id)
        assert trashed is not None and trashed.trashed_at is not None
        assert trashed.scheduled_deletion_at is not None
        self.assertEqual((trashed.scheduled_deletion_at - trashed.trashed_at).days, 30)

    async def test_project_lists_tasks_in_number_order(self) -> None:
        await self._add(2, title="두 번째 태스크")
        await self._add(1, title="첫 번째 태스크")
        async with self.database.session() as session:
            project = await session.scalar(
                select(Project)
                .where(Project.id == self.project.id)
                .options(selectinload(Project.tasks))
            )
        assert project is not None
        self.assertEqual([t.task_number for t in project.tasks], [1, 2])

    async def test_deleting_a_project_deletes_its_tasks(self) -> None:
        await self._add(1)
        async with self.database.session() as session:
            await session.delete(await session.get(Project, self.project.id))
            await session.commit()
        async with self.database.session() as session:
            remaining = (await session.scalars(select(Task))).all()
        self.assertEqual(remaining, [])

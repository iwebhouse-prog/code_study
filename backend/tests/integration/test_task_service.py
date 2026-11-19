"""Runs TaskService against PostgreSQL (T068)."""

import asyncio
import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from src.api.exceptions import FieldValidationError
from src.db.session import Database
from src.models import Project, Task, UploadedCode, User
from src.services.project_service import ProjectForbiddenError, ProjectNotFoundError
from src.services.task_service import (
    UNSET,
    TaskDraft,
    TaskForbiddenError,
    TaskNotFoundError,
    TaskService,
)
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

DRAFT = TaskDraft("할 일 추가 기능", "버튼을 누르면 추가", "file")
LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TaskServiceTestCase(unittest.IsolatedAsyncioTestCase):
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
        self.other_id = await self._add_user("other@example.com")
        self.project_id = await self._add_project(self.user_id)

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

    async def _add_project(
        self, user_id: uuid.UUID, status: str = "active"
    ) -> uuid.UUID:
        async with self.database.session() as session:
            project = Project(
                user_id=user_id,
                title="My Todo App",
                last_activity_at=LONG_AGO,
                deletion_status=status,
            )
            session.add(project)
            await session.commit()
            return project.id

    async def _create(
        self, draft: TaskDraft = DRAFT, project_id: uuid.UUID | None = None
    ) -> Task:
        async with self.database.session() as session:
            return await TaskService(session).create_for_user(
                project_id or self.project_id, self.user_id, draft
            )

    async def _activity(self) -> datetime:
        async with self.database.session() as session:
            project = await session.get(Project, self.project_id)
        assert project is not None
        return project.last_activity_at

    async def _reset_activity(self) -> None:
        async with self.database.session() as session:
            await session.execute(
                update(Project)
                .where(Project.id == self.project_id)
                .values(last_activity_at=LONG_AGO)
            )
            await session.commit()

    async def _stored(self, task_id: uuid.UUID) -> Task:
        async with self.database.session() as session:
            task = await session.get(Task, task_id)
        assert task is not None
        return task

    async def _mark_trashed(self, task_id: uuid.UUID) -> None:
        async with self.database.session() as session:
            task = await session.get(Task, task_id)
            assert task is not None
            task.move_to_trash()
            await session.commit()


class TestCreate(TaskServiceTestCase):
    async def test_saves_the_task_with_cleaned_fields(self) -> None:
        task = await self._create(TaskDraft("  할 일 추가 기능  ", "  ", "paste"))
        stored = await self._stored(task.id)
        self.assertEqual(stored.title, "할 일 추가 기능")
        self.assertIsNone(stored.description)
        self.assertEqual(stored.upload_method, "paste")
        self.assertEqual(stored.project_id, self.project_id)
        self.assertEqual(stored.deletion_status, "active")

    async def test_numbers_count_up_from_one(self) -> None:
        numbers = [(await self._create()).task_number for _ in range(3)]
        self.assertEqual(numbers, [1, 2, 3])

    async def test_trashed_tasks_keep_their_number(self) -> None:
        first = await self._create()
        await self._mark_trashed(first.id)
        self.assertEqual((await self._create()).task_number, 2)

    async def test_numbers_are_per_project(self) -> None:
        other_project = await self._add_project(self.user_id)
        await self._create()
        self.assertEqual((await self._create(project_id=other_project)).task_number, 1)

    async def test_concurrent_creates_get_different_numbers(self) -> None:
        tasks = await asyncio.gather(*(self._create() for _ in range(5)))
        self.assertEqual(sorted(t.task_number for t in tasks), [1, 2, 3, 4, 5])

    async def test_sets_the_project_last_activity_to_now(self) -> None:
        await self._create()
        self.assertGreater(
            await self._activity(), datetime.now(UTC) - timedelta(minutes=1)
        )

    async def test_returned_task_has_no_code_yet(self) -> None:
        task = await self._create()
        self.assertIsNone(task.uploaded_code)

    async def test_invalid_input_saves_nothing(self) -> None:
        with self.assertRaises(FieldValidationError):
            await self._create(TaskDraft("짧음", None, "file"))
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(Task))).all(), [])
        self.assertEqual(await self._activity(), LONG_AGO)

    async def test_another_users_project_is_forbidden(self) -> None:
        theirs = await self._add_project(self.other_id)
        with self.assertRaises(ProjectForbiddenError):
            await self._create(project_id=theirs)

    async def test_missing_or_trashed_project_is_not_found(self) -> None:
        trashed = await self._add_project(self.user_id, status="trashed")
        for project_id in (uuid.uuid4(), trashed):
            with (
                self.subTest(project_id=project_id),
                self.assertRaises(ProjectNotFoundError),
            ):
                await self._create(project_id=project_id)

    async def test_add_does_not_commit(self) -> None:
        async with self.database.session() as session:
            task = await TaskService(session).add_for_user(
                self.project_id, self.user_id, DRAFT
            )
            self.assertEqual(task.task_number, 1)
            await session.rollback()
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(Task))).all(), [])


class TestListAndGet(TaskServiceTestCase):
    async def _list(self, project_id: uuid.UUID | None = None) -> list[Task]:
        async with self.database.session() as session:
            return await TaskService(session).list_for_user(
                project_id or self.project_id, self.user_id
            )

    async def test_lists_active_tasks_by_number(self) -> None:
        first, second, third = [await self._create() for _ in range(3)]
        await self._mark_trashed(second.id)
        tasks = await self._list()
        self.assertEqual([t.id for t in tasks], [first.id, third.id])

    async def test_empty_project_lists_nothing(self) -> None:
        self.assertEqual(await self._list(), [])

    async def test_list_carries_the_code_summary(self) -> None:
        task = await self._create()
        async with self.database.session() as session:
            session.add(
                UploadedCode(task_id=task.id, detected_language="python", total_files=1)
            )
            await session.commit()
        (listed,) = await self._list()
        assert listed.uploaded_code is not None
        self.assertEqual(listed.uploaded_code.detected_language, "python")

    async def test_list_refuses_other_users_and_missing_projects(self) -> None:
        theirs = await self._add_project(self.other_id)
        with self.assertRaises(ProjectForbiddenError):
            await self._list(theirs)
        with self.assertRaises(ProjectNotFoundError):
            await self._list(uuid.uuid4())

    async def test_get_returns_the_users_task(self) -> None:
        task = await self._create()
        async with self.database.session() as session:
            found = await TaskService(session).get_for_user(task.id, self.user_id)
        self.assertEqual(found.id, task.id)
        self.assertIsNone(found.uploaded_code)

    async def test_get_refuses_another_users_task(self) -> None:
        task = await self._create()
        async with self.database.session() as session:
            with self.assertRaises(TaskForbiddenError):
                await TaskService(session).get_for_user(task.id, self.other_id)

    async def test_get_hides_missing_trashed_and_trashed_project_tasks(self) -> None:
        task = await self._create()
        in_trashed_project = await self._create()
        await self._mark_trashed(task.id)
        async with self.database.session() as session:
            await session.execute(
                update(Project)
                .where(Project.id == self.project_id)
                .values(deletion_status="trashed")
            )
            await session.commit()
        for task_id in (uuid.uuid4(), task.id, in_trashed_project.id):
            with self.subTest(task_id=task_id):
                async with self.database.session() as session:
                    with self.assertRaises(TaskNotFoundError):
                        await TaskService(session).get_for_user(task_id, self.user_id)


class TestUpdate(TaskServiceTestCase):
    async def _update(
        self, task: Task, user_id: uuid.UUID | None = None, **changes: str | None
    ) -> Task:
        async with self.database.session() as session:
            return await TaskService(session).update_for_user(
                task.id, user_id or self.user_id, **changes  # type: ignore[arg-type]
            )

    async def test_changes_title_and_description(self) -> None:
        task = await self._create()
        updated = await self._update(
            task, title="  새 제목입니다 ", description="새 설명"
        )
        stored = await self._stored(task.id)
        self.assertEqual(
            (stored.title, stored.description), ("새 제목입니다", "새 설명")
        )
        self.assertEqual(updated.title, "새 제목입니다")

    async def test_fields_left_out_stay(self) -> None:
        task = await self._create()
        await self._update(task, title="새 제목입니다")
        self.assertEqual((await self._stored(task.id)).description, DRAFT.description)
        await self._update(task, description="바뀐 설명")
        self.assertEqual((await self._stored(task.id)).title, "새 제목입니다")

    async def test_none_or_blank_description_clears_it(self) -> None:
        task = await self._create()
        await self._update(task, description=None)
        self.assertIsNone((await self._stored(task.id)).description)
        await self._update(task, description="다시")
        await self._update(task, description="  ")
        self.assertIsNone((await self._stored(task.id)).description)

    async def test_number_and_upload_method_never_change(self) -> None:
        task = await self._create()
        await self._update(task, title="새 제목입니다")
        stored = await self._stored(task.id)
        self.assertEqual((stored.task_number, stored.upload_method), (1, "file"))

    async def test_updated_at_moves_forward(self) -> None:
        task = await self._create()
        updated = await self._update(task, title="새 제목입니다")
        self.assertGreater(updated.updated_at, task.updated_at)

    async def test_invalid_title_changes_nothing(self) -> None:
        task = await self._create()
        with self.assertRaises(FieldValidationError):
            await self._update(task, title="짧음", description="바꾸려던 설명")
        stored = await self._stored(task.id)
        self.assertEqual(
            (stored.title, stored.description), (DRAFT.title, DRAFT.description)
        )

    async def test_too_long_description_is_rejected(self) -> None:
        task = await self._create()
        with self.assertRaises(FieldValidationError):
            await self._update(task, description="가" * 501)

    async def test_sets_the_project_last_activity(self) -> None:
        task = await self._create()
        await self._reset_activity()
        await self._update(task, title="새 제목입니다")
        self.assertGreater(await self._activity(), LONG_AGO + timedelta(days=1))

    async def test_refuses_another_users_task(self) -> None:
        task = await self._create()
        with self.assertRaises(TaskForbiddenError):
            await self._update(task, self.other_id, title="새 제목입니다")

    async def test_nothing_to_change_still_returns_the_task(self) -> None:
        task = await self._create()
        async with self.database.session() as session:
            same = await TaskService(session).update_for_user(
                task.id, self.user_id, title=UNSET, description=UNSET
            )
        self.assertEqual(same.title, DRAFT.title)


class TestTrash(TaskServiceTestCase):
    async def _trash(self, task: Task, user_id: uuid.UUID | None = None) -> Task:
        async with self.database.session() as session:
            return await TaskService(session).move_to_trash_for_user(
                task.id, user_id or self.user_id
            )

    async def test_moves_the_task_to_the_trash_for_30_days(self) -> None:
        task = await self._create()
        await self._trash(task)
        stored = await self._stored(task.id)
        self.assertEqual(stored.deletion_status, "trashed")
        assert stored.trashed_at and stored.scheduled_deletion_at
        self.assertEqual(
            stored.scheduled_deletion_at - stored.trashed_at, timedelta(days=30)
        )

    async def test_sets_the_project_last_activity(self) -> None:
        task = await self._create()
        await self._reset_activity()
        await self._trash(task)
        self.assertGreater(await self._activity(), LONG_AGO + timedelta(days=1))

    async def test_trashed_task_is_gone_for_later_calls(self) -> None:
        task = await self._create()
        await self._trash(task)
        with self.assertRaises(TaskNotFoundError):
            await self._trash(task)

    async def test_refuses_another_users_task(self) -> None:
        task = await self._create()
        with self.assertRaises(TaskForbiddenError):
            await self._trash(task, self.other_id)
        self.assertEqual((await self._stored(task.id)).deletion_status, "active")

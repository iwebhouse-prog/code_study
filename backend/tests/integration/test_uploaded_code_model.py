"""Checks the UploadedCode model against the real migrated table (T062)."""

import unittest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models import Project, Task, UploadedCode, User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by its default.
STRICTER_IN_MODEL = ("created_at",)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestUploadedCodeMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(UploadedCode, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestUploadedCodePersistence(unittest.IsolatedAsyncioTestCase):
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
            user = User(email="learner@example.com", password_hash="hash")
            session.add(user)
            await session.flush()
            project = Project(user_id=user.id, title="Todo 앱")
            session.add(project)
            await session.flush()
            self.task = Task(
                project_id=project.id, task_number=1, title="할 일 추가 기능"
            )
            session.add(self.task)
            await session.commit()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(self, **fields: object) -> UploadedCode:
        async with self.database.session() as session:
            code = UploadedCode(task_id=self.task.id, **fields)
            session.add(code)
            await session.commit()
            return code

    async def test_metadata_is_stored_and_created_at_is_readable(self) -> None:
        code = await self._add(
            detected_language="python",
            complexity_level="beginner",
            total_lines=42,
            total_files=2,
            upload_size_bytes=1500,
        )
        self.assertIsNotNone(code.id)
        self.assertIsNotNone(code.created_at)
        async with self.database.session() as session:
            stored = await session.get(UploadedCode, code.id)
        assert stored is not None
        self.assertEqual(
            (stored.detected_language, stored.complexity_level, stored.total_lines),
            ("python", "beginner", 42),
        )
        self.assertEqual((stored.total_files, stored.upload_size_bytes), (2, 1500))

    async def test_metadata_may_be_filled_in_later(self) -> None:
        # Language and complexity are found by analysis after the upload is saved.
        code = await self._add()
        self.assertIsNone(code.detected_language)
        self.assertIsNone(code.complexity_level)

    async def test_ten_megabytes_is_accepted(self) -> None:
        code = await self._add(upload_size_bytes=UploadedCode.MAX_UPLOAD_BYTES)
        self.assertEqual(code.upload_size_bytes, 10485760)

    async def test_over_ten_megabytes_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "valid_upload_size"):
            await self._add(upload_size_bytes=UploadedCode.MAX_UPLOAD_BYTES + 1)

    async def test_unknown_complexity_level_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "complexity_level"):
            await self._add(complexity_level="expert")

    async def test_second_upload_for_the_same_task_is_rejected(self) -> None:
        await self._add()
        with self.assertRaisesRegex(IntegrityError, "uploaded_code_task_id_key"):
            await self._add()

    async def test_task_loads_its_uploaded_code(self) -> None:
        await self._add(detected_language="javascript")
        async with self.database.session() as session:
            task = await session.scalar(
                select(Task)
                .where(Task.id == self.task.id)
                .options(selectinload(Task.uploaded_code))
            )
        assert task is not None and task.uploaded_code is not None
        self.assertEqual(task.uploaded_code.detected_language, "javascript")

    async def test_task_without_upload_has_none(self) -> None:
        async with self.database.session() as session:
            task = await session.scalar(
                select(Task).options(selectinload(Task.uploaded_code))
            )
        assert task is not None
        self.assertIsNone(task.uploaded_code)

    async def test_deleting_a_task_deletes_its_uploaded_code(self) -> None:
        await self._add()
        async with self.database.session() as session:
            await session.delete(await session.get(Task, self.task.id))
            await session.commit()
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(UploadedCode))).all(), [])

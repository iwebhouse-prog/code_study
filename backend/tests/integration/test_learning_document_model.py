"""Checks the LearningDocument model against the real migrated table (T090)."""

import unittest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models import LearningDocument, Project, Task, User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by their defaults.
STRICTER_IN_MODEL = ("created_at", "updated_at", "generation_status")

CONTENT = {
    "chapter1": {"title": "이 코드가 하는 일", "summary": "두 수를 더합니다."},
    "chapter2": {"title": "미리 알아둘 개념", "concepts": [{"name": "변수"}]},
    "chapter3": {"title": "코드 구조", "flowchart": "A --> B"},
    "chapter4": {"title": "한 줄씩 설명", "explanations": []},
    "chapter5": {"title": "실행 흐름", "steps": []},
    "chapter6": {"title": "핵심 개념", "concepts": []},
    "chapter7": {"title": "자주 하는 실수", "mistakes": []},
}


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestLearningDocumentMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(LearningDocument, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestLearningDocumentPersistence(unittest.IsolatedAsyncioTestCase):
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

    async def _add(self, content: object = None, **fields: object) -> LearningDocument:
        async with self.database.session() as session:
            document = LearningDocument(
                task_id=self.task.id,
                content=(
                    LearningDocument.empty_content() if content is None else content
                ),
                **fields,
            )
            session.add(document)
            await session.commit()
            return document

    async def _get(self, document_id: object) -> LearningDocument:
        async with self.database.session() as session:
            document = await session.get(LearningDocument, document_id)
        assert document is not None
        return document

    async def test_new_document_waits_with_empty_chapters(self) -> None:
        document = await self._add()
        stored = await self._get(document.id)
        self.assertEqual(stored.generation_status, "pending")
        self.assertEqual(stored.content, LearningDocument.empty_content())
        self.assertIsNotNone(stored.created_at)
        self.assertIsNotNone(stored.updated_at)

    async def test_full_lifecycle_is_saved(self) -> None:
        saved = await self._add()
        async with self.database.session() as session:
            document = await session.get(LearningDocument, saved.id)
            assert document is not None
            document.start("celery-abc")
            await session.commit()
            self.assertEqual(document.generation_status, "in_progress")
            document.complete(CONTENT)
            await session.commit()
        stored = await self._get(saved.id)
        self.assertEqual(stored.generation_status, "completed")
        self.assertEqual(stored.celery_task_id, "celery-abc")
        self.assertEqual(stored.content, CONTENT)  # Korean text and nesting kept
        assert stored.generation_started_at and stored.generation_completed_at
        self.assertGreaterEqual(
            stored.generation_completed_at, stored.generation_started_at
        )

    async def test_failure_reason_is_saved(self) -> None:
        saved = await self._add()
        async with self.database.session() as session:
            document = await session.get(LearningDocument, saved.id)
            assert document is not None
            document.start("celery-abc")
            document.fail("AI 서비스 응답 없음")
            await session.commit()
        stored = await self._get(saved.id)
        self.assertEqual(stored.generation_status, "failed")
        self.assertEqual(stored.generation_error, "AI 서비스 응답 없음")

    async def test_content_without_every_chapter_is_rejected(self) -> None:
        content = dict(CONTENT)
        del content["chapter4"]
        with self.assertRaisesRegex(IntegrityError, "valid_content_structure"):
            await self._add(content)

    async def test_content_that_is_not_an_object_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "valid_content_structure"):
            await self._add(["chapter1"])

    async def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "generation_status"):
            await self._add(generation_status="done")

    async def test_second_document_for_the_same_task_is_rejected(self) -> None:
        await self._add()
        with self.assertRaisesRegex(IntegrityError, "learning_documents_task_id_key"):
            await self._add()

    async def test_task_loads_its_document(self) -> None:
        await self._add()
        async with self.database.session() as session:
            task = await session.scalar(
                select(Task).options(selectinload(Task.learning_document))
            )
        assert task is not None and task.learning_document is not None
        self.assertEqual(task.learning_document.generation_status, "pending")

    async def test_deleting_the_task_deletes_its_document(self) -> None:
        await self._add()
        async with self.database.session() as session:
            await session.delete(await session.get(Task, self.task.id))
            await session.commit()
        async with self.database.session() as session:
            remaining = (await session.scalars(select(LearningDocument))).all()
        self.assertEqual(remaining, [])

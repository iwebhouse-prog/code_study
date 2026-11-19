"""Runs the document generation Celery task against PostgreSQL (T094).

The AI service is a fake and uploads live in a temporary folder: no test here
calls Gemini, Redis or the development database.
"""

import tempfile
import unittest
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from src.db.session import Database
from src.models import LearningDocument, Project, User
from src.services.ai.prompts import PromptFile
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.upload_files import IncomingFile
from src.services.document.document_generation_service import DocumentGenerationError
from src.services.task_service import TaskDraft
from src.tasks import document_generation
from src.tasks.celery_app import app as celery_app
from src.tasks.document_generation import (
    GenerationRuntime,
    build_runtime,
    generate_document,
    generate_for_task,
)
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

CONTENT = {f"chapter{i}": {"title": f"{i}장"} for i in range(1, 8)}
CODE = b"def add(a, b):\n    return a + b\n"


class FakeGenerator:
    def __init__(self, result: Any = None) -> None:
        self.result = CONTENT if result is None else result
        self.calls: list[tuple[Sequence[PromptFile], str | None, str | None]] = []

    async def generate(
        self,
        files: Sequence[PromptFile],
        *,
        language: str | None,
        complexity: str | None,
    ) -> dict[str, Any]:
        self.calls.append((files, language, complexity))
        if isinstance(self.result, BaseException):
            raise self.result
        return dict(self.result)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class DocumentGenerationTaskTestCase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.storage = FileStorage(Path(self._tmp.name))
        self.database = Database(TEST_DATABASE_URL)
        async with self.database.session() as session:
            user = User(email=f"{uuid.uuid4()}@example.com", password_hash="hash")
            session.add(user)
            await session.flush()
            project = Project(user_id=user.id, title="문서 생성 시험")
            session.add(project)
            await session.commit()
            result = await CodeUploadService(
                session, self.storage
            ).create_task_with_code(
                project.id,
                user.id,
                TaskDraft("덧셈 함수 이해하기", None, "file"),
                [IncomingFile("calc.py", CODE)],
            )
        self.task_id = result.task.id
        self.user_id = user.id
        self.generator = FakeGenerator()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            user = await session.get(User, self.user_id)
            await session.delete(user)
            await session.commit()
        await self.database.dispose()

    def runtime(self, generator: Any = None) -> GenerationRuntime:
        return GenerationRuntime(
            self.database, self.storage, generator or self.generator
        )

    async def run_task(
        self, task_id: uuid.UUID | None = None, celery_id="cid-1"
    ) -> str:
        return await generate_for_task(
            str(task_id or self.task_id), celery_id, self.runtime()
        )

    async def document(self) -> LearningDocument:
        async with self.database.session() as session:
            return await session.scalar(
                select(LearningDocument).where(LearningDocument.task_id == self.task_id)
            )

    async def add_document(self, status: str) -> None:
        async with self.database.session() as session:
            session.add(
                LearningDocument(
                    task_id=self.task_id,
                    content=LearningDocument.empty_content(),
                    generation_status=status,
                )
            )
            await session.commit()

    async def test_pending_document_is_generated_and_completed(self) -> None:
        await self.add_document("pending")
        self.assertEqual(await self.run_task(), "completed")
        doc = await self.document()
        self.assertEqual(doc.generation_status, "completed")
        self.assertEqual(doc.content, CONTENT)
        self.assertEqual(doc.celery_task_id, "cid-1")
        self.assertIsNotNone(doc.generation_started_at)
        self.assertIsNotNone(doc.generation_completed_at)
        self.assertIsNone(doc.generation_error)

    async def test_missing_row_is_created_first(self) -> None:
        self.assertEqual(await self.run_task(), "completed")
        self.assertEqual((await self.document()).generation_status, "completed")

    async def test_generator_gets_files_language_and_complexity(self) -> None:
        await self.run_task()
        files, language, complexity = self.generator.calls[0]
        self.assertEqual(files, [PromptFile("calc.py", "python", CODE.decode())])
        self.assertEqual(language, "python")
        self.assertEqual(complexity, "beginner")

    async def test_completed_and_running_documents_are_skipped(self) -> None:
        for status in ("completed", "in_progress"):
            with self.subTest(status=status):
                async with self.database.session() as session:
                    await session.execute(
                        LearningDocument.__table__.delete().where(
                            LearningDocument.task_id == self.task_id
                        )
                    )
                    await session.commit()
                await self.add_document(status)
                self.assertEqual(await self.run_task(), "skipped")
        self.assertEqual(self.generator.calls, [])
        self.assertEqual((await self.document()).generation_status, "in_progress")

    async def test_unknown_task_is_skipped(self) -> None:
        self.assertEqual(await self.run_task(uuid.uuid4()), "skipped")
        self.assertEqual(self.generator.calls, [])

    async def test_generation_error_records_reason_and_detail(self) -> None:
        self.generator.result = DocumentGenerationError(
            "ai_unavailable", attempts=4, problems=["quota exceeded"]
        )
        self.assertEqual(await self.run_task(), "failed")
        doc = await self.document()
        self.assertEqual(doc.generation_status, "failed")
        self.assertEqual(
            doc.generation_error, "ai_unavailable: after 4 attempts: quota exceeded"
        )
        self.assertEqual(doc.content, LearningDocument.empty_content())
        self.assertIsNotNone(doc.generation_completed_at)

    async def test_generation_error_without_problems(self) -> None:
        self.generator.result = DocumentGenerationError("ai_rejected", attempts=1)
        await self.run_task()
        self.assertEqual(
            (await self.document()).generation_error, "ai_rejected: after 1 attempts"
        )

    async def test_soft_time_limit_records_timeout(self) -> None:
        self.generator.result = SoftTimeLimitExceeded()
        self.assertEqual(await self.run_task(), "failed")
        self.assertTrue(
            (await self.document()).generation_error.startswith("timeout: ")
        )

    async def test_unexpected_error_records_internal_error_and_logs(self) -> None:
        self.generator.result = RuntimeError("boom")
        with self.assertLogs(document_generation.logger, "ERROR") as logs:
            self.assertEqual(await self.run_task(), "failed")
        doc = await self.document()
        self.assertEqual(doc.generation_error, "internal_error: RuntimeError: boom")
        self.assertIn("Traceback", logs.output[0])

    async def test_missing_code_file_records_internal_error(self) -> None:
        for path in Path(self._tmp.name).rglob("*.py"):
            path.unlink()
        with self.assertLogs(document_generation.logger, "ERROR"):
            self.assertEqual(await self.run_task(), "failed")
        self.assertTrue(
            (await self.document()).generation_error.startswith("internal_error: ")
        )

    async def test_failed_document_can_run_again(self) -> None:
        self.generator.result = RuntimeError("boom")
        with self.assertLogs(document_generation.logger, "ERROR"):
            await self.run_task()
        self.generator.result = CONTENT
        self.assertEqual(await self.run_task(celery_id="cid-2"), "completed")
        doc = await self.document()
        self.assertEqual(doc.generation_status, "completed")
        self.assertIsNone(doc.generation_error)

    async def test_late_result_cannot_overwrite_a_document_that_moved_on(self) -> None:
        """The run was declared failed meanwhile: its result is dropped, not saved."""

        class Racing(FakeGenerator):
            async def generate(
                inner, *args: Any, **kwargs: Any
            ) -> dict[str, Any]:  # noqa: N805
                async with self.database.session() as session:
                    doc = await session.scalar(select(LearningDocument))
                    doc.fail("timeout: stale")
                    await session.commit()
                return await super().generate(*args, **kwargs)

        with self.assertLogs(document_generation.logger, "WARNING"):
            outcome = await generate_for_task(
                str(self.task_id), "cid-1", self.runtime(Racing())
            )
        self.assertEqual(outcome, "skipped")
        doc = await self.document()
        self.assertEqual(doc.generation_status, "failed")
        self.assertEqual(doc.generation_error, "timeout: stale")

    async def test_late_failure_does_not_overwrite_a_document_that_moved_on(
        self,
    ) -> None:
        async def fail_elsewhere() -> None:
            async with self.database.session() as session:
                doc = await session.scalar(select(LearningDocument))
                doc.fail("timeout: stale")
                await session.commit()

        class Racing(FakeGenerator):
            async def generate(
                inner, *args: Any, **kwargs: Any
            ) -> dict[str, Any]:  # noqa: N805
                await fail_elsewhere()
                raise RuntimeError("late boom")

        with self.assertLogs(document_generation.logger, "ERROR"):
            outcome = await generate_for_task(
                str(self.task_id), "cid-1", self.runtime(Racing())
            )
        self.assertEqual(outcome, "failed")
        self.assertEqual((await self.document()).generation_error, "timeout: stale")


class GenerateDocumentCeleryTaskTestCase(unittest.TestCase):
    def test_task_is_registered_and_routed_to_its_queue(self) -> None:
        self.assertIn(
            "src.tasks.document_generation.generate_document", celery_app.tasks
        )
        route = celery_app.amqp.router.route(
            {}, "src.tasks.document_generation.generate_document"
        )
        self.assertEqual(route["queue"].name, "document_generation")

    def test_task_module_is_loaded_by_workers(self) -> None:
        from src.tasks.celery_app import TASK_MODULES

        self.assertIn("src.tasks.document_generation", TASK_MODULES)

    def test_task_never_retries_and_has_time_limits(self) -> None:
        self.assertEqual(generate_document.max_retries, 0)
        self.assertEqual(celery_app.conf.task_soft_time_limit, 270)
        self.assertEqual(celery_app.conf.task_time_limit, 300)

    def test_task_runs_with_runtime_and_disposes_database(self) -> None:
        database = FakeDatabase()
        runtime = GenerationRuntime(database, None, None)  # type: ignore[arg-type]
        calls: list[tuple[str, str]] = []

        async def fake_generate(
            task_id: str, celery_task_id: str, given: GenerationRuntime
        ) -> str:
            self.assertIs(given, runtime)
            calls.append((task_id, celery_task_id))
            return "completed"

        with (
            patch.object(document_generation, "build_runtime", return_value=runtime),
            patch.object(document_generation, "generate_for_task", fake_generate),
        ):
            result = generate_document.apply(args=["some-task-id"], task_id="abc-123")
        self.assertEqual(result.get(), "completed")
        self.assertEqual(calls, [("some-task-id", "abc-123")])
        self.assertTrue(database.disposed)

    def test_database_is_disposed_even_when_the_run_raises(self) -> None:
        database = FakeDatabase()
        runtime = GenerationRuntime(database, None, None)  # type: ignore[arg-type]

        async def broken(*args: Any) -> str:
            raise RuntimeError("db down")

        with (
            patch.object(document_generation, "build_runtime", return_value=runtime),
            patch.object(document_generation, "generate_for_task", broken),
        ):
            result = generate_document.apply(args=["x"])
        self.assertIsInstance(result.result, RuntimeError)
        self.assertTrue(database.disposed)

    def test_build_runtime_reads_configuration_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "DATABASE_URL": TEST_DATABASE_URL,
                "UPLOAD_DIR": tmp,
                "GOOGLE_API_KEY": "test-key-not-real",
            }
            runtime = build_runtime(env)
        self.assertEqual(
            runtime.database.engine.url.render_as_string(hide_password=False),
            TEST_DATABASE_URL,
        )
        self.assertIsInstance(runtime.storage, FileStorage)
        self.assertNotIn("test-key-not-real", repr(runtime))


class FakeDatabase:
    disposed = False

    async def dispose(self) -> None:
        self.disposed = True

"""Runs DocumentQueueService against PostgreSQL (T095).

The task sender is a fake: nothing here talks to Redis.
"""

import unittest
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from sqlalchemy import select, text

from src.db.session import Database
from src.models import LearningDocument, Project, Task, UploadedCode, User
from src.services.document import document_queue_service
from src.services.document.document_queue_service import (
    DocumentNotFailedError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    DocumentQueueService,
    expected_seconds,
    send_generation_task,
)
from src.tasks.document_generation import generate_document
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
CONTENT = {f"chapter{i}": {"title": f"{i}장"} for i in range(1, 8)}


class TestExpectedSeconds(unittest.TestCase):
    def test_formula_is_30_plus_point_three_per_line_within_30_and_180(self) -> None:
        cases = [(0, 30), (100, 60), (101, 60), (250, 105), (500, 180), (9000, 180)]
        for lines, seconds in cases:
            with self.subTest(lines=lines):
                self.assertEqual(expected_seconds(lines), seconds)


class TestSendGenerationTask(unittest.TestCase):
    def test_queues_the_celery_task_with_the_task_id(self) -> None:
        with patch.object(generate_document, "apply_async") as apply_async:
            send_generation_task("abc")
        apply_async.assert_called_once_with(args=["abc"], retry=False)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class DocumentQueueServiceTestCase(unittest.IsolatedAsyncioTestCase):
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
        self.sent: list[str] = []
        async with self.database.session() as session:
            user = User(email=f"{uuid.uuid4()}@example.com", password_hash="hash")
            session.add(user)
            await session.flush()
            project = Project(user_id=user.id, title="큐 시험")
            session.add(project)
            await session.flush()
            task = Task(
                project_id=project.id,
                task_number=1,
                title="큐 시험 태스크",
                upload_method="file",
            )
            session.add(task)
            await session.flush()
            session.add(UploadedCode(task_id=task.id, total_lines=100))
            await session.commit()
        self.user_id, self.task_id = user.id, task.id

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            await session.delete(await session.get(User, self.user_id))
            await session.commit()
        await self.database.dispose()

    def send(self, task_id: str) -> None:
        self.sent.append(task_id)

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Runs one service method in its own session, like one request."""
        async with self.database.session() as session:
            service = DocumentQueueService(session, self.send)
            return await getattr(service, method)(*args, **kwargs)

    async def make_document(
        self,
        status: str,
        *,
        started_seconds_ago: int | None = None,
        error: str | None = None,
        content: dict[str, Any] | None = None,
    ) -> None:
        started = (
            NOW - timedelta(seconds=started_seconds_ago)
            if started_seconds_ago is not None
            else None
        )
        async with self.database.session() as session:
            session.add(
                LearningDocument(
                    task_id=self.task_id,
                    content=content or LearningDocument.empty_content(),
                    generation_status=status,
                    generation_started_at=started,
                    generation_error=error,
                    celery_task_id="old-id" if started else None,
                )
            )
            await session.commit()

    async def stored(self) -> LearningDocument:
        async with self.database.session() as session:
            return await session.scalar(
                select(LearningDocument).where(LearningDocument.task_id == self.task_id)
            )

    # enqueue

    async def test_enqueue_creates_pending_row_then_sends(self) -> None:
        committed: list[bool] = []
        async with self.database.session() as session:

            def send_and_look(task_id: str) -> None:
                # Sent only after the commit: no transaction is open any more.
                committed.append(not session.in_transaction())
                self.sent.append(task_id)

            await DocumentQueueService(session, send_and_look).enqueue(self.task_id)
        self.assertEqual(self.sent, [str(self.task_id)])
        self.assertEqual(committed, [True])
        self.assertEqual((await self.stored()).generation_status, "pending")
        doc = await self.stored()
        self.assertEqual(doc.content, LearningDocument.empty_content())
        self.assertIsNone(doc.generation_started_at)

    async def test_enqueue_keeps_an_existing_row(self) -> None:
        await self.make_document("completed", content=CONTENT)
        await self.call("enqueue", self.task_id)
        doc = await self.stored()
        self.assertEqual(doc.generation_status, "completed")
        self.assertEqual(doc.content, CONTENT)
        self.assertEqual(self.sent, [str(self.task_id)])

    async def test_enqueue_survives_a_failing_queue(self) -> None:
        def broken(_: str) -> None:
            raise ConnectionError("redis is down")

        with self.assertLogs(document_queue_service.logger, "ERROR") as logs:
            async with self.database.session() as session:
                await DocumentQueueService(session, broken).enqueue(self.task_id)
        self.assertIn("redis is down", "\n".join(logs.output))
        self.assertEqual((await self.stored()).generation_status, "pending")

    async def test_enqueue_survives_a_failing_database(self) -> None:
        async with self.database.session() as session:
            service = DocumentQueueService(session, self.send)
            with (
                patch.object(session, "commit", side_effect=RuntimeError("db gone")),
                self.assertLogs(document_queue_service.logger, "ERROR"),
            ):
                await service.enqueue(self.task_id)
        self.assertEqual(self.sent, [])

    # status

    async def test_status_of_a_task_without_document_is_not_found(self) -> None:
        with self.assertRaises(DocumentNotFoundError):
            await self.call("status", self.task_id)

    async def test_pending_status_shows_the_expected_total(self) -> None:
        await self.make_document("pending")
        status = await self.call("status", self.task_id, now=NOW)
        self.assertEqual(
            (status.task_id, status.status, status.started_at, status.completed_at),
            (self.task_id, "pending", None, None),
        )
        self.assertEqual(status.estimated_seconds_remaining, 60)  # 100 lines
        self.assertIsNone(status.error_reason)

    async def test_in_progress_status_counts_down_to_at_least_5(self) -> None:
        for elapsed, remaining in [(0, 60), (25, 35), (58, 5), (200, 5)]:
            with self.subTest(elapsed=elapsed):
                await self.reset_document()
                await self.make_document("in_progress", started_seconds_ago=elapsed)
                status = await self.call("status", self.task_id, now=NOW)
                self.assertEqual(status.status, "in_progress")
                self.assertEqual(status.started_at, NOW - timedelta(seconds=elapsed))
                self.assertEqual(status.estimated_seconds_remaining, remaining)

    async def test_estimate_is_clamped_for_huge_uploads(self) -> None:
        await self.make_document("pending")
        async with self.database.session() as session:
            await session.execute(text("UPDATE uploaded_code SET total_lines = 99999"))
            await session.commit()
        status = await self.call("status", self.task_id, now=NOW)
        self.assertEqual(status.estimated_seconds_remaining, 180)

    async def test_estimate_without_uploaded_code_uses_the_minimum(self) -> None:
        await self.make_document("pending")
        async with self.database.session() as session:
            await session.execute(text("DELETE FROM uploaded_code"))
            await session.commit()
        status = await self.call("status", self.task_id, now=NOW)
        self.assertEqual(status.estimated_seconds_remaining, 30)

    async def test_completed_status_has_no_estimate_and_no_error(self) -> None:
        await self.make_document("in_progress", started_seconds_ago=30)
        async with self.database.session() as session:
            doc = await session.scalar(select(LearningDocument))
            doc.complete(CONTENT, NOW)
            await session.commit()
        status = await self.call("status", self.task_id, now=NOW)
        self.assertEqual(status.status, "completed")
        self.assertEqual(status.completed_at, NOW)
        self.assertIsNone(status.estimated_seconds_remaining)
        self.assertIsNone(status.error_reason)

    async def test_failed_status_gives_the_reason_only(self) -> None:
        cases = [
            ("ai_unavailable: after 4 attempts: quota", "ai_unavailable"),
            ("timeout: soft time limit", "timeout"),
            ("who_knows: secret detail", "internal_error"),
            (None, "internal_error"),
        ]
        for error, reason in cases:
            with self.subTest(error=error):
                await self.reset_document()
                await self.make_document("failed", started_seconds_ago=20, error=error)
                status = await self.call("status", self.task_id, now=NOW)
                self.assertEqual(status.status, "failed")
                self.assertEqual(status.error_reason, reason)
                self.assertIsNone(status.estimated_seconds_remaining)

    async def test_run_longer_than_300_seconds_is_reported_as_timeout(self) -> None:
        await self.make_document("in_progress", started_seconds_ago=301)
        status = await self.call("status", self.task_id, now=NOW)
        self.assertEqual(status.status, "failed")
        self.assertEqual(status.error_reason, "timeout")
        self.assertIsNone(status.estimated_seconds_remaining)
        # Reporting does not rewrite the row.
        self.assertEqual((await self.stored()).generation_status, "in_progress")

    async def reset_document(self) -> None:
        async with self.database.session() as session:
            await session.execute(text("DELETE FROM learning_documents"))
            await session.commit()

    # get_completed

    async def test_get_completed_returns_the_stored_document(self) -> None:
        await self.make_document("in_progress", started_seconds_ago=30)
        async with self.database.session() as session:
            doc = await session.scalar(select(LearningDocument))
            doc.complete(CONTENT, NOW)
            await session.commit()
        doc = await self.call("get_completed", self.task_id)
        self.assertEqual(doc.content, CONTENT)

    async def test_get_completed_refuses_documents_not_ready(self) -> None:
        cases = [("pending", None, "pending"), ("in_progress", 10, "in_progress")]
        cases.append(("in_progress", 301, "failed"))
        cases.append(("failed", 10, "failed"))
        for status, started, shown in cases:
            with self.subTest(status=status, started=started):
                await self.reset_document()
                await self.make_document(status, started_seconds_ago=started)
                with self.assertRaises(DocumentNotReadyError) as caught:
                    await self.call("get_completed", self.task_id, now=NOW)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(caught.exception.details, {"status": shown})

    async def test_get_completed_without_document_is_not_found(self) -> None:
        with self.assertRaises(DocumentNotFoundError):
            await self.call("get_completed", self.task_id)

    # regenerate

    async def test_regenerate_failed_document_resets_and_sends(self) -> None:
        await self.make_document(
            "failed", started_seconds_ago=20, error="timeout: slow"
        )
        status = await self.call("regenerate", self.task_id, now=NOW)
        self.assertEqual(status.status, "pending")
        self.assertIsNone(status.started_at)
        self.assertEqual(status.estimated_seconds_remaining, 60)
        self.assertEqual(self.sent, [str(self.task_id)])
        doc = await self.stored()
        self.assertEqual(doc.generation_status, "pending")
        self.assertIsNone(doc.generation_error)
        self.assertIsNone(doc.celery_task_id)

    async def test_regenerate_stale_run_resets_and_sends(self) -> None:
        await self.make_document("in_progress", started_seconds_ago=400)
        status = await self.call("regenerate", self.task_id, now=NOW)
        self.assertEqual(status.status, "pending")
        self.assertEqual(self.sent, [str(self.task_id)])

    async def test_regenerate_refuses_documents_that_did_not_fail(self) -> None:
        for status, started in [("pending", None), ("in_progress", 10)]:
            with self.subTest(status=status):
                await self.reset_document()
                await self.make_document(status, started_seconds_ago=started)
                with self.assertRaises(DocumentNotFailedError) as caught:
                    await self.call("regenerate", self.task_id, now=NOW)
                self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.sent, [])

    async def test_regenerate_never_touches_a_completed_document(self) -> None:
        await self.make_document("in_progress", started_seconds_ago=30)
        async with self.database.session() as session:
            doc = await session.scalar(select(LearningDocument))
            doc.complete(CONTENT, NOW)
            await session.commit()
        with self.assertRaises(DocumentNotFailedError):
            await self.call("regenerate", self.task_id, now=NOW)
        doc = await self.stored()
        self.assertEqual(doc.generation_status, "completed")
        self.assertEqual(doc.content, CONTENT)
        self.assertEqual(self.sent, [])

    async def test_regenerate_without_document_is_not_found(self) -> None:
        with self.assertRaises(DocumentNotFoundError):
            await self.call("regenerate", self.task_id)

    async def test_regenerate_survives_a_failing_queue(self) -> None:
        await self.make_document("failed", started_seconds_ago=20, error="x: y")

        def broken(_: str) -> None:
            raise ConnectionError("redis is down")

        with self.assertLogs(document_queue_service.logger, "ERROR"):
            async with self.database.session() as session:
                status = await DocumentQueueService(session, broken).regenerate(
                    self.task_id, now=NOW
                )
        self.assertEqual(status.status, "pending")
        self.assertEqual((await self.stored()).generation_status, "pending")

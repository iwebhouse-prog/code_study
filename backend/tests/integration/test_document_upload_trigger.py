"""Uploading code queues document generation after the commit (T096)."""

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.db.session import Database
from src.main import create_app
from src.models import LearningDocument, Project, Task, User
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.upload_files import IncomingFile
from src.services.document.document_queue_service import DocumentQueueService
from src.services.task_service import TaskDraft
from src.tasks.document_generation import generate_document
from src.utils.jwt import JWTConfig, create_access_token
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    execute_script,
    fetch,
    recreate_test_database,
    run_alembic,
)

JWT_CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
ME = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
DRAFT = TaskDraft("덧셈 함수 이해하기", None, "file")
CODE = [IncomingFile("calc.py", b"print(1)\n")]


class FakeQueue:
    """Records the task id and whether the task row was already committed."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.calls: list[tuple[uuid.UUID, bool]] = []

    async def enqueue(self, task_id: uuid.UUID) -> None:
        async with self.database.session() as session:
            visible = await session.get(Task, task_id) is not None
        self.calls.append((task_id, visible))


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class UploadTriggerServiceTestCase(unittest.IsolatedAsyncioTestCase):
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
            project = Project(user_id=user.id, title="트리거 시험")
            session.add(project)
            await session.commit()
        self.user_id, self.project_id = user.id, project.id

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            await session.delete(await session.get(User, self.user_id))
            await session.commit()
        await self.database.dispose()

    async def upload(self, queue: object, source: list[IncomingFile] = CODE) -> Task:
        async with self.database.session() as session:
            service = CodeUploadService(session, self.storage, queue)  # type: ignore[arg-type]
            result = await service.create_task_with_code(
                self.project_id, self.user_id, DRAFT, source
            )
        return result.task

    async def test_queue_is_asked_after_the_commit(self) -> None:
        queue = FakeQueue(self.database)
        task = await self.upload(queue)
        self.assertEqual(queue.calls, [(task.id, True)])

    async def test_failed_upload_queues_nothing(self) -> None:
        queue = FakeQueue(self.database)
        with self.assertRaises(Exception):  # noqa: B017 - any upload error
            await self.upload(queue, [IncomingFile("notes.exe", b"x")])
        self.assertEqual(queue.calls, [])

    async def test_real_queue_creates_pending_document_and_sends_task(self) -> None:
        sent: list[str] = []
        async with self.database.session() as session:
            queue = DocumentQueueService(session, sent.append)
            result = await CodeUploadService(
                session, self.storage, queue
            ).create_task_with_code(self.project_id, self.user_id, DRAFT, CODE)
        self.assertEqual(sent, [str(result.task.id)])
        async with self.database.session() as session:
            doc = await session.scalar(
                select(LearningDocument).where(
                    LearningDocument.task_id == result.task.id
                )
            )
        self.assertEqual(doc.generation_status, "pending")
        self.assertEqual(doc.content, LearningDocument.empty_content())

    async def test_upload_succeeds_when_queueing_fails(self) -> None:
        def broken(_: str) -> None:
            raise ConnectionError("redis is down")

        async with self.database.session() as session:
            queue = DocumentQueueService(session, broken)
            with self.assertLogs("src.services.document.document_queue_service"):
                result = await CodeUploadService(
                    session, self.storage, queue
                ).create_task_with_code(self.project_id, self.user_id, DRAFT, CODE)
        self.assertEqual(result.task.title, DRAFT.title)
        async with self.database.session() as session:
            doc = await session.scalar(select(LearningDocument))
        self.assertEqual(doc.generation_status, "pending")


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class UploadTriggerApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        execute_script(
            f"INSERT INTO users (id, email, password_hash) VALUES "
            f"('{ME}', 'api-me@example.com', 'hash')"
        )
        self.project_id = uuid.uuid4()
        execute_script(
            "INSERT INTO projects (id, user_id, title) VALUES "
            f"('{self.project_id}', '{ME}', 'Todo')"
        )
        app = create_app(
            app_config=AppConfig(upload_dir=Path(self._tmp.name)),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWT_CONFIG,
        )
        self.client = TestClient(app)
        self.client.__enter__()
        token = create_access_token(ME, JWT_CONFIG)
        self.client.cookies.set(ACCESS_TOKEN_COOKIE, token)

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def post_task(self):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/api/v1/projects/{self.project_id}/tasks",
            data={"title": "덧셈 함수 이해하기", "upload_method": "file"},
            files=[("files", ("calc.py", b"print(1)\n"))],
        )

    def test_upload_queues_the_celery_task_on_the_document_queue(self) -> None:
        with patch.object(generate_document, "apply_async") as apply_async:
            response = self.post_task()
        self.assertEqual(response.status_code, 201)
        task_id = response.json()["id"]
        apply_async.assert_called_once_with(args=[task_id], retry=False)
        rows = fetch(
            "SELECT generation_status FROM learning_documents WHERE task_id = $1",
            uuid.UUID(task_id),
        )
        self.assertEqual([row["generation_status"] for row in rows], ["pending"])

    def test_upload_still_succeeds_when_redis_is_down(self) -> None:
        broken = MagicMock(side_effect=ConnectionError("redis is down"))
        with (
            patch.object(generate_document, "apply_async", broken),
            self.assertLogs("src.services.document.document_queue_service"),
        ):
            response = self.post_task()
        self.assertEqual(response.status_code, 201)
        rows = fetch("SELECT generation_status FROM learning_documents")
        self.assertEqual([row["generation_status"] for row in rows], ["pending"])

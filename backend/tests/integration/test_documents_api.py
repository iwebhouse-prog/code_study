"""Document endpoints end to end against PostgreSQL (T097, T098, regenerate)."""

import json
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.api.error_messages import DOCUMENT_MESSAGES
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.main import create_app
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
ME = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
OTHER = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
CONTENT = {f"chapter{i}": {"title": f"{i}장", "summary": "요약"} for i in range(1, 8)}
STATUS_FIELDS = {
    "task_id",
    "status",
    "started_at",
    "completed_at",
    "estimated_seconds_remaining",
    "error",
}
SECRET = "SECRET-DETAIL-xyz"


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class DocumentsApiTestCase(unittest.TestCase):
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
            "INSERT INTO users (id, email, password_hash) VALUES "
            f"('{ME}', 'docs-me@example.com', 'hash'), "
            f"('{OTHER}', 'docs-other@example.com', 'hash')"
        )
        app = create_app(
            app_config=AppConfig(upload_dir=Path(self._tmp.name)),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWT_CONFIG,
        )
        self.client = TestClient(app)
        self.client.__enter__()
        self.set_user(ME)
        self.task_id = self.insert_task(ME, lines=100)

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def set_user(self, user_id: uuid.UUID) -> None:
        token = create_access_token(user_id, JWT_CONFIG)
        self.client.cookies.set(ACCESS_TOKEN_COOKIE, token)

    def insert_task(
        self, owner: uuid.UUID, *, lines: int | None = None, status: str = "active"
    ) -> str:
        project_id, task_id = uuid.uuid4(), uuid.uuid4()
        execute_script(
            "INSERT INTO projects (id, user_id, title) VALUES "
            f"('{project_id}', '{owner}', 'Todo')",
            "INSERT INTO tasks (id, project_id, task_number, title, upload_method, "
            f"deletion_status) VALUES ('{task_id}', '{project_id}', 1, "
            f"'문서 시험 태스크', 'file', '{status}')",
        )
        if lines is not None:
            execute_script(
                "INSERT INTO uploaded_code (task_id, total_lines) VALUES "
                f"('{task_id}', {lines})"
            )
        return str(task_id)

    def insert_document(
        self,
        task_id: str | None = None,
        status: str = "pending",
        *,
        started_seconds_ago: int | None = None,
        error: str | None = None,
        done: bool = False,
    ) -> None:
        started = (
            f"now() - interval '{started_seconds_ago} seconds'"
            if started_seconds_ago is not None
            else "NULL"
        )
        content = json.dumps(
            CONTENT if done else {f"chapter{i}": {} for i in range(1, 8)}
        )
        error_sql = "NULL" if error is None else f"'{error}'"
        completed = "now()" if done else "NULL"
        execute_script(
            "INSERT INTO learning_documents (task_id, content, generation_status, "
            "generation_started_at, generation_completed_at, generation_error, "
            "celery_task_id) VALUES "
            f"('{task_id or self.task_id}', '{content}'::jsonb, '{status}', "
            f"{started}, {completed}, {error_sql}, 'celery-secret-id')"
        )

    def get(self, suffix: str, task_id: str | None = None) -> Any:
        return self.client.get(f"/api/v1/tasks/{task_id or self.task_id}{suffix}")

    def regenerate(self, task_id: str | None = None) -> Any:
        return self.client.post(
            f"/api/v1/tasks/{task_id or self.task_id}/document/regenerate"
        )

    def all_calls(self) -> list[Any]:
        return [
            lambda: self.get("/document"),
            lambda: self.get("/document/status"),
            self.regenerate,
        ]

    # common rules

    def test_every_endpoint_requires_sign_in(self) -> None:
        self.client.cookies.clear()
        for call in self.all_calls():
            with self.subTest():
                self.assertEqual(call().status_code, 401)

    def test_non_uuid_task_id_is_a_validation_error(self) -> None:
        for call in (
            lambda: self.get("/document", "nope"),
            lambda: self.get("/document/status", "nope"),
            lambda: self.regenerate("nope"),
        ):
            with self.subTest():
                response = call()
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"], "validation_error")

    def test_other_users_task_is_forbidden(self) -> None:
        theirs = self.insert_task(OTHER, lines=10)
        self.insert_document(
            theirs, "failed", error="timeout: x", started_seconds_ago=5
        )
        for call in (
            lambda: self.get("/document", theirs),
            lambda: self.get("/document/status", theirs),
            lambda: self.regenerate(theirs),
        ):
            with self.subTest():
                self.assertEqual(call().status_code, 403)
        self.assertEqual(
            fetch("SELECT generation_status FROM learning_documents")[0][0], "failed"
        )

    def test_missing_and_trashed_tasks_are_not_found(self) -> None:
        trashed = self.insert_task(ME, status="trashed")
        for task_id in (str(uuid.uuid4()), trashed):
            for call in (
                lambda t=task_id: self.get("/document", t),
                lambda t=task_id: self.get("/document/status", t),
                lambda t=task_id: self.regenerate(t),
            ):
                with self.subTest(task_id=task_id):
                    response = call()
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json()["error"], "not_found")

    def test_task_without_document_row_is_document_not_found(self) -> None:
        for call in self.all_calls():
            with self.subTest():
                response = call()
                self.assertEqual(response.status_code, 404)
                body = response.json()
                self.assertEqual(body["error"], "document_not_found")
                self.assertEqual(
                    body["message"], DOCUMENT_MESSAGES["document_not_found"]
                )

    # GET /document/status

    def test_pending_status(self) -> None:
        self.insert_document(status="pending")
        response = self.get("/document/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), STATUS_FIELDS)
        self.assertEqual(body["task_id"], self.task_id)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["estimated_seconds_remaining"], 60)
        self.assertIsNone(body["started_at"])
        self.assertIsNone(body["error"])

    def test_in_progress_status_counts_down(self) -> None:
        self.insert_document(status="in_progress", started_seconds_ago=20)
        body = self.get("/document/status").json()
        self.assertEqual(body["status"], "in_progress")
        self.assertIsNotNone(body["started_at"])
        self.assertIn(body["estimated_seconds_remaining"], range(38, 41))

    def test_completed_status_has_no_estimate(self) -> None:
        self.insert_document(status="completed", started_seconds_ago=30, done=True)
        body = self.get("/document/status").json()
        self.assertEqual(body["status"], "completed")
        self.assertIsNotNone(body["completed_at"])
        self.assertIsNone(body["estimated_seconds_remaining"])
        self.assertIsNone(body["error"])

    def test_failed_status_has_a_korean_message_and_no_detail(self) -> None:
        cases = {
            f"ai_unavailable: {SECRET}": "ai_unavailable",
            f"ai_rejected: {SECRET}": "ai_rejected",
            f"invalid_content: {SECRET}": "invalid_content",
            f"timeout: {SECRET}": "timeout",
            f"internal_error: {SECRET}": "internal_error",
            f"mystery: {SECRET}": "internal_error",
        }
        for error, reason in cases.items():
            with self.subTest(error=error):
                execute_script("DELETE FROM learning_documents")
                self.insert_document(
                    status="failed", started_seconds_ago=9, error=error
                )
                response = self.get("/document/status")
                body = response.json()
                self.assertEqual(body["status"], "failed")
                self.assertEqual(
                    body["error"],
                    {"reason": reason, "message": DOCUMENT_MESSAGES[reason]},
                )
                self.assertIsNone(body["estimated_seconds_remaining"])
                self.assertNotIn(SECRET, response.text)
                self.assertNotIn("celery", response.text)

    def test_stale_run_is_reported_as_timeout(self) -> None:
        self.insert_document(status="in_progress", started_seconds_ago=400)
        body = self.get("/document/status").json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["error"]["reason"], "timeout")

    # GET /document

    def test_completed_document_returns_stored_content(self) -> None:
        self.insert_document(status="completed", started_seconds_ago=30, done=True)
        response = self.get("/document")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"task_id", "status", "completed_at", "content"})
        self.assertEqual(body["task_id"], self.task_id)
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["content"], CONTENT)
        self.assertNotIn("celery", response.text)

    def test_document_not_ready_is_409_with_current_status(self) -> None:
        cases = [
            ("pending", None, "pending"),
            ("in_progress", 10, "in_progress"),
            ("in_progress", 400, "failed"),
            ("failed", 10, "failed"),
        ]
        for status, started, shown in cases:
            with self.subTest(status=status, started=started):
                execute_script("DELETE FROM learning_documents")
                self.insert_document(status=status, started_seconds_ago=started)
                response = self.get("/document")
                self.assertEqual(response.status_code, 409)
                body = response.json()
                self.assertEqual(body["error"], "document_not_ready")
                self.assertEqual(
                    body["message"], DOCUMENT_MESSAGES["document_not_ready"]
                )
                self.assertEqual(body["details"], {"status": shown})

    # POST /document/regenerate

    def test_regenerate_failed_document(self) -> None:
        self.insert_document(
            status="failed", started_seconds_ago=20, error=f"timeout: {SECRET}"
        )
        with patch.object(generate_document, "apply_async") as apply_async:
            response = self.regenerate()
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(set(body), STATUS_FIELDS)
        self.assertEqual(body["status"], "pending")
        self.assertEqual(body["estimated_seconds_remaining"], 60)
        self.assertIsNone(body["error"])
        apply_async.assert_called_once_with(args=[self.task_id], retry=False)
        row = fetch("SELECT * FROM learning_documents")[0]
        self.assertEqual(row["generation_status"], "pending")
        self.assertIsNone(row["generation_error"])
        self.assertIsNone(row["celery_task_id"])

    def test_regenerate_stale_run(self) -> None:
        self.insert_document(status="in_progress", started_seconds_ago=400)
        response = self.regenerate()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "pending")

    def test_regenerate_refuses_other_states(self) -> None:
        cases = [
            ("pending", None, False),
            ("in_progress", 10, False),
            ("completed", 30, True),
        ]
        for status, started, done in cases:
            with self.subTest(status=status):
                execute_script("DELETE FROM learning_documents")
                self.insert_document(
                    status=status, started_seconds_ago=started, done=done
                )
                with patch.object(generate_document, "apply_async") as apply_async:
                    response = self.regenerate()
                self.assertEqual(response.status_code, 409)
                body = response.json()
                self.assertEqual(body["error"], "document_not_failed")
                self.assertEqual(
                    body["message"], DOCUMENT_MESSAGES["document_not_failed"]
                )
                apply_async.assert_not_called()
                row = fetch("SELECT generation_status FROM learning_documents")[0]
                self.assertEqual(row[0], status)

    def test_regenerate_succeeds_even_if_the_queue_is_down(self) -> None:
        self.insert_document(status="failed", started_seconds_ago=5, error="x: y")
        with (
            patch.object(generate_document, "apply_async", side_effect=OSError("down")),
            self.assertLogs("src.services.document.document_queue_service"),
        ):
            response = self.regenerate()
        self.assertEqual(response.status_code, 202)

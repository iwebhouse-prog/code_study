"""Runs migration 001 against a throwaway database and checks data-model.md (T009)."""

import unittest

import asyncpg

from tests.integration.db_utils import (
    database_reachable,
    drop_test_database,
    execute_script,
    fetch,
    recreate_test_database,
    run_alembic,
)
from tests.integration.schema_expectations import EXPECTED_INDEXES, EXPECTED_TABLES

# Fixed ids: user ...01, project ...02, task ...03, uploaded_code ...04
INSERT_USER = (
    "INSERT INTO users (id, email, password_hash) "
    "VALUES ('00000000-0000-0000-0000-000000000001', 'learner@example.com', 'x')"
)
INSERT_SAME_EMAIL = (
    "INSERT INTO users (id, email, password_hash) "
    "VALUES ('00000000-0000-0000-0000-000000000009', 'learner@example.com', 'y')"
)
INSERT_PROJECT = (
    "INSERT INTO projects (id, user_id, title) "
    "VALUES ('00000000-0000-0000-0000-000000000002', "
    "'00000000-0000-0000-0000-000000000001', 'P')"
)
INSERT_TASK = (
    "INSERT INTO tasks (id, project_id, task_number, title) "
    "VALUES ('00000000-0000-0000-0000-000000000003', "
    "'00000000-0000-0000-0000-000000000002', 1, 'Task one')"
)
INSERT_SAME_TASK_NUMBER = (
    "INSERT INTO tasks (project_id, task_number, title) "
    "VALUES ('00000000-0000-0000-0000-000000000002', 1, 'Task again')"
)
INSERT_SHORT_TITLE_TASK = (
    "INSERT INTO tasks (project_id, task_number, title) "
    "VALUES ('00000000-0000-0000-0000-000000000002', 2, 'Tiny')"
)
INSERT_UPLOADED_CODE = (
    "INSERT INTO uploaded_code (id, task_id) "
    "VALUES ('00000000-0000-0000-0000-000000000004', "
    "'00000000-0000-0000-0000-000000000003')"
)
OWNED_ROWS = (INSERT_USER, INSERT_PROJECT, INSERT_TASK)


def public_tables() -> set[str]:
    rows = fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    return {row["tablename"] for row in rows} - {"alembic_version"}


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestInitialSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def setUp(self) -> None:
        execute_script("DELETE FROM users")

    def assert_rejected(self, *statements: str) -> None:
        with self.assertRaises(asyncpg.IntegrityConstraintViolationError):
            execute_script(*statements)

    def test_revision_001_is_head(self) -> None:
        rows = fetch("SELECT version_num FROM alembic_version")
        self.assertEqual([row["version_num"] for row in rows], ["001"])

    def test_all_tables_exist(self) -> None:
        self.assertEqual(public_tables(), EXPECTED_TABLES)

    def test_all_indexes_exist(self) -> None:
        rows = fetch("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
        missing = EXPECTED_INDEXES - {row["indexname"] for row in rows}
        self.assertEqual(missing, set())

    def test_active_indexes_are_partial(self) -> None:
        rows = fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE indexname = ANY($1)",
            ["idx_projects_user_active", "idx_tasks_project_active"],
        )
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertIn("WHERE", row["indexdef"], row["indexname"])

    def test_defaults_are_applied(self) -> None:
        execute_script(*OWNED_ROWS)
        user = fetch("SELECT skill_level, created_at FROM users")[0]
        task = fetch("SELECT deletion_status FROM tasks")[0]
        self.assertEqual(user["skill_level"], "Complete Beginner")
        self.assertIsNotNone(user["created_at"])
        self.assertEqual(task["deletion_status"], "active")

    def test_invalid_email_is_rejected(self) -> None:
        self.assert_rejected(
            "INSERT INTO users (email, password_hash) VALUES ('not-an-email', 'x')"
        )

    def test_duplicate_email_is_rejected(self) -> None:
        self.assert_rejected(INSERT_USER, INSERT_SAME_EMAIL)

    def test_task_title_shorter_than_five_is_rejected(self) -> None:
        self.assert_rejected(*OWNED_ROWS, INSERT_SHORT_TITLE_TASK)

    def test_task_numbers_are_unique_per_project(self) -> None:
        self.assert_rejected(*OWNED_ROWS, INSERT_SAME_TASK_NUMBER)

    def test_upload_size_over_ten_megabytes_is_rejected(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            "INSERT INTO uploaded_code (task_id, upload_size_bytes) "
            "VALUES ('00000000-0000-0000-0000-000000000003', 10485761)",
        )

    def test_unsupported_file_extension_is_rejected(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            INSERT_UPLOADED_CODE,
            "INSERT INTO code_files "
            "(uploaded_code_id, file_name, file_extension, storage_path) "
            "VALUES ('00000000-0000-0000-0000-000000000004', 'a.exe', '.exe', 'x')",
        )

    def test_learning_document_requires_seven_chapters(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            "INSERT INTO learning_documents (task_id, content) "
            "VALUES ('00000000-0000-0000-0000-000000000003', '{\"chapter1\": {}}')",
        )

    def test_learning_document_with_seven_chapters_defaults_to_pending(self) -> None:
        execute_script(
            *OWNED_ROWS,
            "INSERT INTO learning_documents (task_id, content) "
            "VALUES ('00000000-0000-0000-0000-000000000003', "
            '\'{"chapter1":{},"chapter2":{},"chapter3":{},"chapter4":{},'
            '"chapter5":{},"chapter6":{},"chapter7":{}}\')',
        )
        status = fetch("SELECT generation_status FROM learning_documents")[0]
        self.assertEqual(status["generation_status"], "pending")

    def test_practice_problem_number_must_be_one_to_five(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            "INSERT INTO practice_problems "
            "(task_id, problem_number, problem_type, problem_statement) "
            "VALUES ('00000000-0000-0000-0000-000000000003', 6, 'create', 'x')",
        )

    def test_question_shorter_than_three_characters_is_rejected(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            "INSERT INTO questions (task_id, user_id, question_text) "
            "VALUES ('00000000-0000-0000-0000-000000000003', "
            "'00000000-0000-0000-0000-000000000001', 'hi')",
        )

    def test_progress_chapters_cannot_exceed_seven(self) -> None:
        self.assert_rejected(
            *OWNED_ROWS,
            "INSERT INTO progress (task_id, user_id, chapters_completed) "
            "VALUES ('00000000-0000-0000-0000-000000000003', "
            "'00000000-0000-0000-0000-000000000001', '[1,2,3,4,5,6,7,8]')",
        )

    def test_deleting_user_cascades_to_all_owned_rows(self) -> None:
        execute_script(
            *OWNED_ROWS,
            "INSERT INTO progress (task_id, user_id) "
            "VALUES ('00000000-0000-0000-0000-000000000003', "
            "'00000000-0000-0000-0000-000000000001')",
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
            "VALUES ('00000000-0000-0000-0000-000000000001', 'h', "
            "now() + interval '7 days')",
            "DELETE FROM users",
        )
        for table in ("projects", "tasks", "progress", "refresh_tokens"):
            count = fetch(f"SELECT count(*) AS n FROM {table}")[0]["n"]  # noqa: S608
            self.assertEqual(count, 0, table)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestInitialSchemaDowngrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_downgrade_removes_every_table_and_upgrade_restores_them(self) -> None:
        self.assertEqual(run_alembic("upgrade", "head").returncode, 0)
        result = run_alembic("downgrade", "base")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(public_tables(), set())

        result = run_alembic("upgrade", "head")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(public_tables(), EXPECTED_TABLES)


if __name__ == "__main__":
    unittest.main()

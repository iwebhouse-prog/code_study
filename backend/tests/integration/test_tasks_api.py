"""Task endpoints end to end against PostgreSQL and a temporary folder (T070-T075)."""

import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.api.dependencies import ACCESS_TOKEN_COOKIE
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.main import create_app
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
ME = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER = uuid.UUID("00000000-0000-0000-0000-000000000002")
TASK_FIELDS = {
    "id",
    "project_id",
    "task_number",
    "title",
    "description",
    "upload_method",
    "created_at",
    "updated_at",
    "code",
}
CODE_FIELDS = {
    "detected_language",
    "complexity_level",
    "total_lines",
    "total_files",
    "upload_size_bytes",
}
FILE_FIELDS = {
    "id",
    "file_name",
    "file_path",
    "file_extension",
    "file_size_bytes",
    "language",
}
APP_JSX = b"export default function App() {\r\n  return null;\r\n}\r\n"
LONG_AGO = "'2020-01-01T00:00:00+00:00'"


def auth(user_id: uuid.UUID = ME) -> dict[str, str]:
    token = create_access_token(user_id, JWT_CONFIG)
    return {"Cookie": f"{ACCESS_TOKEN_COOKIE}={token}"}


def part(name: str, content: bytes = b"x = 1\n") -> tuple[str, tuple[str, bytes]]:
    return ("files", (name, content))


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TasksApiTestCase(unittest.TestCase):
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
        self.root = Path(self._tmp.name)
        execute_script(
            "INSERT INTO users (id, email, password_hash) VALUES "
            f"('{ME}', 'me@example.com', 'hash'), "
            f"('{OTHER}', 'other@example.com', 'hash')"
        )
        app = create_app(
            app_config=AppConfig(upload_dir=self.root),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWT_CONFIG,
        )
        self.client = TestClient(app)
        self.client.__enter__()
        self.project_id = self.insert_project()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def insert_project(
        self, user_id: uuid.UUID = ME, status: str = "active"
    ) -> uuid.UUID:
        project_id = uuid.uuid4()
        execute_script(
            "INSERT INTO projects (id, user_id, title, last_activity_at, "
            f"deletion_status) VALUES ('{project_id}', '{user_id}', 'Todo', "
            f"{LONG_AGO}, '{status}')"
        )
        return project_id

    def insert_task(
        self, project_id: uuid.UUID | None = None, status: str = "active"
    ) -> str:
        """A task without code, made directly in the database."""
        project_id = project_id or self.project_id
        task_id = uuid.uuid4()
        number = fetch(
            "SELECT COALESCE(MAX(task_number), 0) + 1 AS n FROM tasks "
            "WHERE project_id = $1",
            project_id,
        )[0]["n"]
        execute_script(
            "INSERT INTO tasks (id, project_id, task_number, title, upload_method, "
            f"deletion_status) VALUES ('{task_id}', '{project_id}', {number}, "
            f"'직접 넣은 태스크', 'file', '{status}')"
        )
        return str(task_id)

    def project_url(self, project_id: uuid.UUID | str | None = None) -> str:
        return f"/api/v1/projects/{project_id or self.project_id}/tasks"

    def create(
        self,
        files: list[Any] | None = None,
        user_id: uuid.UUID = ME,
        project_id: uuid.UUID | None = None,
        **form: str,
    ) -> Any:
        data = {"title": "할 일 추가 기능", "upload_method": "file", **form}
        if files is None and data["upload_method"] != "paste":
            files = [part("App.jsx", APP_JSX)]
        return self.client.post(
            self.project_url(project_id),
            data=data,
            files=files or None,
            headers=auth(user_id),
        )

    def create_ok(self, files: list[Any] | None = None, **form: str) -> dict[str, Any]:
        response = self.create(files, **form)
        self.assertEqual(response.status_code, 201, response.text)
        body: dict[str, Any] = response.json()
        return body

    def assert_error(self, response: Any, status: int, error: str) -> dict[str, Any]:
        self.assertEqual(response.status_code, status, response.text)
        body: dict[str, Any] = response.json()
        self.assertEqual(body["error"], error)
        self.assertRegex(body["message"], "[가-힣]")
        return body

    def assert_field_error(self, response: Any, field: str, message: str) -> None:
        body = self.assert_error(response, 400, "validation_error")
        self.assertEqual(
            body["details"]["fields"], [{"field": field, "message": message}]
        )

    def stored_files(self) -> list[Path]:
        return [path for path in self.root.rglob("*") if path.is_file()]

    def activity(self) -> str:
        rows = fetch(
            "SELECT last_activity_at > '2021-01-01' AS fresh FROM projects "
            "WHERE id = $1",
            self.project_id,
        )
        return "fresh" if rows[0]["fresh"] else "old"


class TestSignInAndIds(TasksApiTestCase):
    def test_every_endpoint_requires_sign_in(self) -> None:
        task_id = self.insert_task()
        for method, path in (
            ("GET", self.project_url()),
            ("POST", self.project_url()),
            ("GET", f"/api/v1/tasks/{task_id}"),
            ("PATCH", f"/api/v1/tasks/{task_id}"),
            ("DELETE", f"/api/v1/tasks/{task_id}"),
            ("GET", f"/api/v1/tasks/{task_id}/code"),
        ):
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path)
                self.assert_error(response, 401, "unauthorized")

    def test_a_non_uuid_id_is_a_validation_error_naming_the_parameter(self) -> None:
        cases = (
            ("GET", "/api/v1/projects/nope/tasks", "project_id"),
            ("POST", "/api/v1/projects/nope/tasks", "project_id"),
            ("GET", "/api/v1/tasks/nope", "task_id"),
            ("PATCH", "/api/v1/tasks/nope", "task_id"),
            ("DELETE", "/api/v1/tasks/nope", "task_id"),
            ("GET", "/api/v1/tasks/nope/code", "task_id"),
        )
        for method, path, field in cases:
            with self.subTest(path=path, method=method):
                response = self.client.request(method, path, headers=auth())
                body = self.assert_error(response, 400, "validation_error")
                self.assertEqual(body["details"]["fields"][0]["field"], field)


class TestListTasks(TasksApiTestCase):
    def test_empty_list_for_a_new_project(self) -> None:
        response = self.client.get(self.project_url(), headers=auth())
        self.assertEqual((response.status_code, response.json()), (200, []))

    def test_lists_active_tasks_by_task_number(self) -> None:
        first = self.insert_task()
        trashed = self.insert_task(status="trashed")
        third = self.insert_task()
        self.insert_task(self.insert_project())  # another project's task
        items = self.client.get(self.project_url(), headers=auth()).json()
        self.assertEqual([item["id"] for item in items], [first, third])
        self.assertNotIn(trashed, [item["id"] for item in items])
        self.assertEqual([item["task_number"] for item in items], [1, 3])

    def test_items_have_exactly_the_contract_fields(self) -> None:
        self.create_ok()
        (item,) = self.client.get(self.project_url(), headers=auth()).json()
        self.assertEqual(set(item), TASK_FIELDS)
        self.assertEqual(set(item["code"]), CODE_FIELDS)

    def test_a_task_without_code_has_null_code(self) -> None:
        self.insert_task()
        (item,) = self.client.get(self.project_url(), headers=auth()).json()
        self.assertIsNone(item["code"])
        self.assertIsNone(item["description"])

    def test_other_users_project_is_forbidden(self) -> None:
        theirs = self.insert_project(OTHER)
        response = self.client.get(self.project_url(theirs), headers=auth())
        self.assert_error(response, 403, "forbidden")

    def test_missing_and_trashed_projects_are_not_found(self) -> None:
        trashed = self.insert_project(status="trashed")
        for project_id in (uuid.uuid4(), trashed):
            response = self.client.get(self.project_url(project_id), headers=auth())
            self.assert_error(response, 404, "not_found")


class TestCreateFileTask(TasksApiTestCase):
    def test_creates_the_task_and_returns_the_upload_result(self) -> None:
        body = self.create_ok(description="버튼을 누르면 추가")
        self.assertEqual(set(body), TASK_FIELDS | {"files", "excluded_paths"})
        self.assertEqual(
            (body["task_number"], body["title"], body["description"]),
            (1, "할 일 추가 기능", "버튼을 누르면 추가"),
        )
        self.assertEqual(
            (body["project_id"], body["upload_method"]), (str(self.project_id), "file")
        )
        self.assertEqual(
            body["code"],
            {
                "detected_language": "javascript",
                "complexity_level": "beginner",
                "total_lines": 3,
                "total_files": 1,
                "upload_size_bytes": len(APP_JSX),
            },
        )
        (file,) = body["files"]
        self.assertEqual(set(file), FILE_FIELDS)
        self.assertEqual(
            {k: v for k, v in file.items() if k != "id"},
            {
                "file_name": "App.jsx",
                "file_path": "App.jsx",
                "file_extension": ".jsx",
                "file_size_bytes": len(APP_JSX),
                "language": "javascript",
            },
        )
        self.assertEqual(body["excluded_paths"], [])

    def test_never_exposes_user_id_storage_path_or_trash_fields(self) -> None:
        text = self.client.post(
            self.project_url(),
            data={"title": "할 일 추가 기능", "upload_method": "file"},
            files=[part("a.py")],
            headers=auth(),
        ).text
        for hidden in ("user_id", "storage_path", "trashed_at", "deletion_status"):
            self.assertNotIn(hidden, text)

    def test_the_new_task_can_be_fetched_and_listed(self) -> None:
        created = self.create_ok()
        fetched = self.client.get(f"/api/v1/tasks/{created['id']}", headers=auth())
        expected = {
            k: v for k, v in created.items() if k not in ("files", "excluded_paths")
        }
        self.assertEqual(fetched.json(), expected)
        (listed,) = self.client.get(self.project_url(), headers=auth()).json()
        self.assertEqual(listed, expected)

    def test_task_numbers_count_up(self) -> None:
        numbers = [self.create_ok()["task_number"] for _ in range(3)]
        self.assertEqual(numbers, [1, 2, 3])

    def test_sets_the_project_last_activity(self) -> None:
        self.assertEqual(self.activity(), "old")
        self.create_ok()
        self.assertEqual(self.activity(), "fresh")

    def test_stores_utf8_lf_files_under_user_and_task_folders(self) -> None:
        body = self.create_ok()
        (stored,) = self.stored_files()
        self.assertEqual(stored.parent, self.root / str(ME) / body["id"])
        self.assertEqual(stored.suffix, ".jsx")
        self.assertEqual(
            stored.read_bytes(), b"export default function App() {\n  return null;\n}\n"
        )

    def test_several_files_are_ordered_by_path_then_name(self) -> None:
        body = self.create_ok([part("b.py"), part("a.py"), part("c.js")])
        self.assertEqual(
            [f["file_name"] for f in body["files"]], ["a.py", "b.py", "c.js"]
        )
        self.assertEqual(body["code"]["total_files"], 3)
        self.assertEqual(body["code"]["detected_language"], "python")

    def test_the_title_is_trimmed_and_a_blank_description_becomes_null(self) -> None:
        body = self.create_ok(title="  할 일 추가 기능  ", description="   ")
        self.assertEqual(body["title"], "할 일 추가 기능")
        self.assertIsNone(body["description"])

    def test_a_cp949_file_is_accepted(self) -> None:
        body = self.create_ok([part("a.txt", "# 한글\n".encode("cp949"))])
        self.assertEqual(body["files"][0]["language"], "text")

    def test_other_users_and_missing_projects_are_refused(self) -> None:
        theirs = self.insert_project(OTHER)
        self.assert_error(self.create(project_id=theirs), 403, "forbidden")
        self.assert_error(self.create(project_id=uuid.uuid4()), 404, "not_found")
        self.assertEqual(self.stored_files(), [])


class TestCreateFolderTask(TasksApiTestCase):
    def test_folder_files_keep_their_relative_paths(self) -> None:
        body = self.create_ok(
            [
                part("my-app/src/App.jsx", APP_JSX),
                part("my-app/src/index.js", b"import 'x';\n"),
                part("my-app/README.md", b"# app\n"),
            ],
            upload_method="folder",
        )
        paths = [(f["file_path"], f["file_name"]) for f in body["files"]]
        self.assertEqual(
            paths,
            [
                ("my-app/README.md", "README.md"),
                ("my-app/src/App.jsx", "App.jsx"),
                ("my-app/src/index.js", "index.js"),
            ],
        )
        self.assertEqual(body["upload_method"], "folder")

    def test_excluded_paths_are_dropped_and_reported(self) -> None:
        body = self.create_ok(
            [
                part("my-app/src/a.py"),
                part("my-app/node_modules/react/index.js"),
                part("my-app/.git/config"),
            ],
            upload_method="folder",
        )
        self.assertEqual([f["file_path"] for f in body["files"]], ["my-app/src/a.py"])
        self.assertEqual(
            body["excluded_paths"],
            ["my-app/node_modules/react/index.js", "my-app/.git/config"],
        )
        self.assertEqual(len(self.stored_files()), 1)

    def test_a_folder_of_only_excluded_files_is_no_files(self) -> None:
        response = self.create([part("my-app/.git/config")], upload_method="folder")
        self.assert_error(response, 400, "no_files")

    def test_unsafe_relative_paths_are_refused(self) -> None:
        response = self.create([part("../evil.py")], upload_method="folder")
        body = self.assert_error(response, 400, "invalid_file_path")
        self.assertEqual(body["details"], {"file_name": "../evil.py"})
        self.assertEqual(self.stored_files(), [])


class TestCreatePasteTask(TasksApiTestCase):
    def test_pasted_code_is_stored_as_one_file_with_the_chosen_language(self) -> None:
        body = self.create_ok(
            upload_method="paste",
            code="def add(a, b):\r\n    return a + b\r\n",
            language="python",
        )
        self.assertEqual(body["upload_method"], "paste")
        self.assertEqual(body["code"]["detected_language"], "python")
        (file,) = body["files"]
        self.assertEqual(
            (file["file_name"], file["file_path"], file["file_extension"]),
            ("pasted.py", "pasted.py", ".py"),
        )
        (stored,) = self.stored_files()
        self.assertEqual(stored.read_bytes(), b"def add(a, b):\n    return a + b\n")

    def test_the_chosen_language_is_stored_even_for_text(self) -> None:
        body = self.create_ok(upload_method="paste", code="print('x')", language="text")
        self.assertEqual(body["code"]["detected_language"], "text")
        self.assertEqual(body["files"][0]["file_name"], "pasted.txt")

    def test_a_large_paste_is_accepted(self) -> None:
        code = "x = 1\n" * 400_000  # about 2.4MB
        body = self.create_ok(upload_method="paste", code=code, language="python")
        self.assertEqual(body["code"]["upload_size_bytes"], len(code))

    def test_blank_code_and_missing_language_are_field_errors(self) -> None:
        self.assert_field_error(
            self.create(upload_method="paste", code="  ", language="python"),
            "code",
            "붙여넣을 코드를 입력하세요.",
        )
        self.assert_field_error(
            self.create(upload_method="paste", language="python"),
            "code",
            "붙여넣을 코드를 입력하세요.",
        )
        for language in ({}, {"language": "ruby"}):
            self.assert_field_error(
                self.create(upload_method="paste", code="x = 1", **language),
                "language",
                "프로그래밍 언어를 선택하세요.",
            )


class TestCreateErrors(TasksApiTestCase):
    def test_title_rules(self) -> None:
        self.assert_field_error(
            self.create(title="짧음"),
            "title",
            "태스크 제목은 최소 5자 이상이어야 합니다.",
        )
        self.assert_field_error(
            self.create(title="가" * 256),
            "title",
            "태스크 제목은 최대 255자까지 입력할 수 있습니다.",
        )
        response = self.client.post(
            self.project_url(),
            data={"upload_method": "file"},
            files=[part("a.py")],
            headers=auth(),
        )
        self.assert_field_error(
            response, "title", "태스크 제목은 최소 5자 이상이어야 합니다."
        )

    def test_description_rule(self) -> None:
        self.assert_field_error(
            self.create(description="가" * 501),
            "description",
            "태스크 설명은 최대 500자까지 입력할 수 있습니다.",
        )

    def test_upload_method_rule(self) -> None:
        for method in ("zip", ""):
            response = self.create([part("a.py")], upload_method=method)
            self.assert_field_error(
                response, "upload_method", "업로드 방식을 선택하세요."
            )

    def test_validation_errors_save_nothing(self) -> None:
        self.create(title="짧음")
        self.assertEqual(fetch("SELECT id FROM tasks"), [])
        self.assertEqual(self.stored_files(), [])

    def test_no_files_part_is_no_files(self) -> None:
        response = self.client.post(
            self.project_url(),
            data={"title": "할 일 추가 기능", "upload_method": "file"},
            headers=auth(),
        )
        body = self.assert_error(response, 400, "no_files")
        self.assertEqual(body["message"], "업로드할 파일이 없습니다.")
        self.assertIn("suggestion", body)

    def test_too_many_files(self) -> None:
        files = [part(f"f{i}.py") for i in range(21)]
        body = self.assert_error(
            self.create(files, upload_method="folder"), 400, "too_many_files"
        )
        self.assertEqual(body["details"], {"max_files": 20, "uploaded_files": 21})
        self.assertIn("suggestion", body)

    def test_file_too_large_is_413(self) -> None:
        big = b"a" * (10 * 1024 * 1024 + 1)
        body = self.assert_error(
            self.create([part("big.txt", big)]), 413, "file_too_large"
        )
        self.assertEqual(body["details"], {"max_size_mb": 10, "uploaded_size_mb": 10.1})
        self.assertEqual(self.stored_files(), [])

    def test_unsupported_file_type(self) -> None:
        body = self.assert_error(
            self.create([part("run.exe", b"MZ")]), 400, "unsupported_file_type"
        )
        self.assertEqual(body["details"]["file_name"], "run.exe")
        self.assertEqual(body["details"]["extension"], ".exe")
        self.assertIn(".py", body["details"]["supported_extensions"])

    def test_binary_file(self) -> None:
        body = self.assert_error(
            self.create([part("a.py", b"\x00\x01\x02")]), 400, "binary_file"
        )
        self.assertEqual(body["details"], {"file_name": "a.py"})

    def test_unsupported_encoding_has_a_suggestion(self) -> None:
        body = self.assert_error(
            self.create([part("a.py", b"ab \xff\xfe")]), 400, "unsupported_encoding"
        )
        self.assertEqual(body["message"], "파일의 문자 인코딩을 읽을 수 없습니다.")
        self.assertEqual(body["details"], {"file_name": "a.py"})
        self.assertIn("UTF-8", body["suggestion"])

    def test_a_rejected_upload_saves_nothing(self) -> None:
        self.create([part("a.py"), part("b.py", b"\x00")], upload_method="folder")
        self.assertEqual(fetch("SELECT id FROM tasks"), [])
        self.assertEqual(self.stored_files(), [])


class TestGetTask(TasksApiTestCase):
    def test_returns_the_task_object(self) -> None:
        task_id = self.insert_task()
        response = self.client.get(f"/api/v1/tasks/{task_id}", headers=auth())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), TASK_FIELDS)
        self.assertEqual((body["id"], body["task_number"]), (task_id, 1))

    def test_other_users_task_is_forbidden(self) -> None:
        task_id = self.insert_task(self.insert_project(OTHER))
        response = self.client.get(f"/api/v1/tasks/{task_id}", headers=auth())
        self.assert_error(response, 403, "forbidden")

    def test_missing_trashed_and_trashed_project_tasks_are_not_found(self) -> None:
        trashed_task = self.insert_task(status="trashed")
        in_trashed_project = self.insert_task(self.insert_project(status="trashed"))
        for task_id in (uuid.uuid4(), trashed_task, in_trashed_project):
            response = self.client.get(f"/api/v1/tasks/{task_id}", headers=auth())
            self.assert_error(response, 404, "not_found")


class TestUpdateTask(TasksApiTestCase):
    def patch(self, task_id: str, body: Any, user_id: uuid.UUID = ME) -> Any:
        return self.client.patch(
            f"/api/v1/tasks/{task_id}", json=body, headers=auth(user_id)
        )

    def test_changes_title_and_description(self) -> None:
        task_id = self.create_ok(description="옛 설명")["id"]
        response = self.patch(
            task_id, {"title": " 새 제목입니다 ", "description": "새 설명"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), TASK_FIELDS)
        self.assertEqual(
            (body["title"], body["description"]), ("새 제목입니다", "새 설명")
        )
        self.assertIsNotNone(body["code"])

    def test_left_out_fields_stay(self) -> None:
        task_id = self.create_ok(description="옛 설명")["id"]
        body = self.patch(task_id, {"title": "새 제목입니다"}).json()
        self.assertEqual(body["description"], "옛 설명")
        body = self.patch(task_id, {"description": "바뀐 설명"}).json()
        self.assertEqual(body["title"], "새 제목입니다")
        self.assertEqual(self.patch(task_id, {}).json()["title"], "새 제목입니다")

    def test_null_or_empty_description_clears_it(self) -> None:
        task_id = self.create_ok(description="옛 설명")["id"]
        self.assertIsNone(
            self.patch(task_id, {"description": None}).json()["description"]
        )
        self.patch(task_id, {"description": "다시"})
        self.assertIsNone(
            self.patch(task_id, {"description": ""}).json()["description"]
        )

    def test_task_number_upload_method_and_code_cannot_change(self) -> None:
        created = self.create_ok()
        response = self.patch(
            created["id"],
            {
                "task_number": 9,
                "upload_method": "paste",
                "code": None,
                "title": "새 제목입니다",
            },
        )
        body = response.json()
        self.assertEqual((body["task_number"], body["upload_method"]), (1, "file"))
        self.assertEqual(body["code"], created["code"])

    def test_validation_errors(self) -> None:
        task_id = self.create_ok()["id"]
        self.assert_field_error(
            self.patch(task_id, {"title": "짧음"}),
            "title",
            "태스크 제목은 최소 5자 이상이어야 합니다.",
        )
        self.assert_field_error(
            self.patch(task_id, {"title": None}),
            "title",
            "태스크 제목은 최소 5자 이상이어야 합니다.",
        )
        self.assert_field_error(
            self.patch(task_id, {"title": "가" * 256}),
            "title",
            "태스크 제목은 최대 255자까지 입력할 수 있습니다.",
        )
        self.assert_field_error(
            self.patch(task_id, {"description": "가" * 501}),
            "description",
            "태스크 설명은 최대 500자까지 입력할 수 있습니다.",
        )

    def test_sets_the_project_last_activity(self) -> None:
        task_id = self.insert_task()
        self.assertEqual(self.activity(), "old")
        self.patch(task_id, {"title": "새 제목입니다"})
        self.assertEqual(self.activity(), "fresh")

    def test_other_users_and_missing_tasks_are_refused(self) -> None:
        theirs = self.insert_task(self.insert_project(OTHER))
        self.assert_error(
            self.patch(theirs, {"title": "새 제목입니다"}), 403, "forbidden"
        )
        missing = str(uuid.uuid4())
        self.assert_error(
            self.patch(missing, {"title": "새 제목입니다"}), 404, "not_found"
        )


class TestDeleteTask(TasksApiTestCase):
    def delete(self, task_id: str, user_id: uuid.UUID = ME) -> Any:
        return self.client.delete(f"/api/v1/tasks/{task_id}", headers=auth(user_id))

    def test_moves_the_task_to_the_trash(self) -> None:
        task_id = self.create_ok()["id"]
        response = self.delete(task_id)
        self.assertEqual((response.status_code, response.content), (204, b""))
        rows = fetch(
            "SELECT deletion_status, trashed_at FROM tasks WHERE id = $1",
            uuid.UUID(task_id),
        )
        self.assertEqual(rows[0]["deletion_status"], "trashed")
        self.assertIsNotNone(rows[0]["trashed_at"])

    def test_the_task_disappears_from_get_and_list_but_its_files_stay(self) -> None:
        task_id = self.create_ok()["id"]
        self.delete(task_id)
        self.assert_error(
            self.client.get(f"/api/v1/tasks/{task_id}", headers=auth()),
            404,
            "not_found",
        )
        self.assertEqual(self.client.get(self.project_url(), headers=auth()).json(), [])
        self.assertEqual(len(self.stored_files()), 1)

    def test_deleting_twice_is_not_found(self) -> None:
        task_id = self.insert_task()
        self.assertEqual(self.delete(task_id).status_code, 204)
        self.assert_error(self.delete(task_id), 404, "not_found")

    def test_the_next_task_does_not_reuse_the_number(self) -> None:
        task_id = self.create_ok()["id"]
        self.delete(task_id)
        self.assertEqual(self.create_ok()["task_number"], 2)

    def test_sets_the_project_last_activity(self) -> None:
        task_id = self.insert_task()
        self.delete(task_id)
        self.assertEqual(self.activity(), "fresh")

    def test_other_users_task_is_forbidden(self) -> None:
        theirs = self.insert_task(self.insert_project(OTHER))
        self.assert_error(self.delete(theirs), 403, "forbidden")


class TestGetCode(TasksApiTestCase):
    def test_returns_files_with_content_in_path_order(self) -> None:
        created = self.create_ok(
            [
                part("app/b.py", b"b = 2\r\n"),
                part("app/a.py", "# 한글\r\na = 1\r\n".encode()),
            ],
            upload_method="folder",
        )
        response = self.client.get(
            f"/api/v1/tasks/{created['id']}/code", headers=auth()
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"task_id", "detected_language", "files"})
        self.assertEqual(
            (body["task_id"], body["detected_language"]), (created["id"], "python")
        )
        self.assertEqual(
            [f["file_path"] for f in body["files"]], ["app/a.py", "app/b.py"]
        )
        self.assertEqual(set(body["files"][0]), FILE_FIELDS | {"content"})
        self.assertEqual(
            [f["content"] for f in body["files"]], ["# 한글\na = 1\n", "b = 2\n"]
        )
        self.assertEqual(
            [f["id"] for f in body["files"]], [f["id"] for f in created["files"]]
        )

    def test_paste_content_comes_back(self) -> None:
        created = self.create_ok(
            upload_method="paste", code="x = 1\r\n", language="python"
        )
        body = self.client.get(
            f"/api/v1/tasks/{created['id']}/code", headers=auth()
        ).json()
        self.assertEqual(body["files"][0]["content"], "x = 1\n")

    def test_a_task_without_code_has_no_files(self) -> None:
        task_id = self.insert_task()
        body = self.client.get(f"/api/v1/tasks/{task_id}/code", headers=auth()).json()
        self.assertEqual(
            body, {"task_id": task_id, "detected_language": None, "files": []}
        )

    def test_a_file_gone_from_disk_is_file_missing(self) -> None:
        created = self.create_ok([part("a.py"), part("b.py")], upload_method="folder")
        self.stored_files()[0].unlink()
        response = self.client.get(
            f"/api/v1/tasks/{created['id']}/code", headers=auth()
        )
        body = self.assert_error(response, 404, "file_missing")
        self.assertEqual(
            body["message"], "코드 파일을 찾을 수 없습니다. 다시 업로드하세요."
        )

    def test_other_users_missing_and_trashed_tasks(self) -> None:
        theirs = self.insert_task(self.insert_project(OTHER))
        trashed = self.insert_task(status="trashed")
        url = "/api/v1/tasks/{}/code"
        self.assert_error(
            self.client.get(url.format(theirs), headers=auth()), 403, "forbidden"
        )
        for task_id in (uuid.uuid4(), trashed):
            response = self.client.get(url.format(task_id), headers=auth())
            self.assert_error(response, 404, "not_found")


class TestProjectTaskCount(TasksApiTestCase):
    def test_counts_active_tasks_of_the_project(self) -> None:
        other_project = self.insert_project()
        self.insert_task()
        self.insert_task()
        self.insert_task(status="trashed")
        self.insert_task(other_project)
        projects = self.client.get("/api/v1/projects", headers=auth()).json()
        counts = {p["id"]: p["task_count"] for p in projects}
        self.assertEqual(counts, {str(self.project_id): 2, str(other_project): 1})
        self.assertTrue(all(p["completed_task_count"] == 0 for p in projects))

    def test_get_project_and_update_project_count_too(self) -> None:
        self.create_ok()
        self.create_ok()
        url = f"/api/v1/projects/{self.project_id}"
        self.assertEqual(self.client.get(url, headers=auth()).json()["task_count"], 2)
        patched = self.client.patch(url, json={"title": "새 이름"}, headers=auth())
        self.assertEqual(patched.json()["task_count"], 2)

    def test_deleting_a_task_lowers_the_count(self) -> None:
        task_id = self.create_ok()["id"]
        self.client.delete(f"/api/v1/tasks/{task_id}", headers=auth())
        url = f"/api/v1/projects/{self.project_id}"
        self.assertEqual(self.client.get(url, headers=auth()).json()["task_count"], 0)

    def test_a_new_project_has_zero(self) -> None:
        created = self.client.post(
            "/api/v1/projects", json={"title": "새 프로젝트"}, headers=auth()
        )
        self.assertEqual(created.json()["task_count"], 0)

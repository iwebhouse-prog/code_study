"""Project endpoints end to end against PostgreSQL (T046-T050)."""

import unittest
import uuid
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
BASE = "/api/v1/projects"
ME = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER = uuid.UUID("00000000-0000-0000-0000-000000000002")
PROJECT_FIELDS = {
    "id",
    "title",
    "description",
    "created_at",
    "updated_at",
    "last_activity_at",
    "task_count",
    "completed_task_count",
}


def auth(user_id: uuid.UUID = ME) -> dict[str, str]:
    token = create_access_token(user_id, JWT_CONFIG)
    return {"Cookie": f"{ACCESS_TOKEN_COOKIE}={token}"}


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class ProjectsApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def setUp(self) -> None:
        execute_script(
            "INSERT INTO users (id, email, password_hash) VALUES "
            f"('{ME}', 'me@example.com', 'hash'), "
            f"('{OTHER}', 'other@example.com', 'hash')"
        )
        app = create_app(
            app_config=AppConfig(),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWT_CONFIG,
        )
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def insert_project(
        self,
        title: str = "Todo",
        user_id: uuid.UUID = ME,
        activity: str = "now()",
        status: str = "active",
    ) -> uuid.UUID:
        project_id = uuid.uuid4()
        execute_script(
            "INSERT INTO projects (id, user_id, title, last_activity_at, "
            f"deletion_status) VALUES ('{project_id}', '{user_id}', '{title}', "
            f"{activity}, '{status}')"
        )
        return project_id

    def owner_of(self, project_id: str) -> uuid.UUID:
        rows = fetch(
            "SELECT user_id FROM projects WHERE id = $1", uuid.UUID(project_id)
        )
        owner: uuid.UUID = rows[0]["user_id"]
        return owner

    def assert_error(self, response: Any, status: int, error: str) -> None:
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertEqual(body["error"], error)
        self.assertRegex(body["message"], "[가-힣]")

    def assert_field_error(self, response: Any, field: str) -> None:
        self.assert_error(response, 400, "validation_error")
        fields = [item["field"] for item in response.json()["details"]["fields"]]
        self.assertEqual(fields, [field])

    def assert_requires_sign_in(self, method: str, path: str) -> None:
        response = self.client.request(method, path, json={"title": "x"})
        self.assert_error(response, 401, "unauthorized")


class TestListProjects(ProjectsApiTestCase):
    def test_requires_sign_in(self) -> None:
        self.assert_requires_sign_in("GET", BASE)

    def test_empty_list_for_a_new_user(self) -> None:
        response = self.client.get(BASE, headers=auth())
        self.assertEqual((response.status_code, response.json()), (200, []))

    def test_lists_most_recent_activity_first(self) -> None:
        self.insert_project("old", activity="now() - interval '2 days'")
        self.insert_project("new", activity="now()")
        self.insert_project("mid", activity="now() - interval '1 day'")
        response = self.client.get(BASE, headers=auth())
        titles = [item["title"] for item in response.json()]
        self.assertEqual(titles, ["new", "mid", "old"])

    def test_has_exactly_the_contract_fields(self) -> None:
        self.insert_project()
        item = self.client.get(BASE, headers=auth()).json()[0]
        self.assertEqual(set(item), PROJECT_FIELDS)
        self.assertIsNone(item["description"])
        self.assertEqual((item["task_count"], item["completed_task_count"]), (0, 0))

    def test_hides_other_users_and_trashed_projects(self) -> None:
        self.insert_project("mine")
        self.insert_project("theirs", user_id=OTHER)
        self.insert_project("trashed", status="trashed")
        titles = [p["title"] for p in self.client.get(BASE, headers=auth()).json()]
        self.assertEqual(titles, ["mine"])


class TestCreateProject(ProjectsApiTestCase):
    def post(self, body: Any) -> Any:
        return self.client.post(BASE, json=body, headers=auth())

    def test_requires_sign_in(self) -> None:
        self.assert_requires_sign_in("POST", BASE)

    def test_creates_a_project_for_the_signed_in_user(self) -> None:
        response = self.post({"title": "  My Todo  ", "description": "할 일 앱"})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body), PROJECT_FIELDS)
        self.assertEqual((body["title"], body["description"]), ("My Todo", "할 일 앱"))
        self.assertEqual((body["task_count"], body["completed_task_count"]), (0, 0))
        self.assertEqual(self.owner_of(body["id"]), ME)

    def test_description_is_optional(self) -> None:
        body = self.post({"title": "No description"}).json()
        self.assertIsNone(body["description"])

    def test_empty_title_is_refused_with_the_title_message(self) -> None:
        response = self.post({"title": "   "})
        self.assert_field_error(response, "title")
        message = response.json()["details"]["fields"][0]["message"]
        self.assertEqual(message, "프로젝트 제목은 최소 1자 이상이어야 합니다.")

    def test_too_long_title_is_refused(self) -> None:
        self.assert_field_error(self.post({"title": "x" * 256}), "title")

    def test_missing_title_is_refused(self) -> None:
        self.assert_field_error(self.post({"description": "only"}), "title")

    def test_a_user_id_in_the_body_is_ignored(self) -> None:
        body = self.post({"title": "Mine", "user_id": str(OTHER)}).json()
        self.assertNotIn("user_id", body)
        self.assertEqual(self.owner_of(body["id"]), ME)


class TestGetProject(ProjectsApiTestCase):
    def test_requires_sign_in(self) -> None:
        self.assert_requires_sign_in("GET", f"{BASE}/{uuid.uuid4()}")

    def test_returns_the_project(self) -> None:
        project_id = self.insert_project("Todo")
        response = self.client.get(f"{BASE}/{project_id}", headers=auth())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), PROJECT_FIELDS)
        self.assertEqual((body["id"], body["title"]), (str(project_id), "Todo"))

    def test_other_users_project_is_forbidden(self) -> None:
        project_id = self.insert_project(user_id=OTHER)
        response = self.client.get(f"{BASE}/{project_id}", headers=auth())
        self.assert_error(response, 403, "forbidden")
        self.assertEqual(
            response.json()["message"], "이 프로젝트에 접근할 권한이 없습니다."
        )

    def test_missing_project_is_404(self) -> None:
        response = self.client.get(f"{BASE}/{uuid.uuid4()}", headers=auth())
        self.assert_error(response, 404, "not_found")

    def test_trashed_project_is_404(self) -> None:
        project_id = self.insert_project(status="trashed")
        response = self.client.get(f"{BASE}/{project_id}", headers=auth())
        self.assert_error(response, 404, "not_found")

    def test_non_uuid_id_is_a_validation_error_on_project_id(self) -> None:
        response = self.client.get(f"{BASE}/not-a-uuid", headers=auth())
        self.assert_field_error(response, "project_id")


class TestUpdateProject(ProjectsApiTestCase):
    def patch(self, project_id: Any, body: Any) -> Any:
        return self.client.patch(f"{BASE}/{project_id}", json=body, headers=auth())

    def with_description(self) -> uuid.UUID:
        project_id = self.insert_project("Old")
        execute_script(
            f"UPDATE projects SET description = 'desc' WHERE id = '{project_id}'"
        )
        return project_id

    def test_requires_sign_in(self) -> None:
        self.assert_requires_sign_in("PATCH", f"{BASE}/{uuid.uuid4()}")

    def test_changes_the_title_and_keeps_the_description(self) -> None:
        response = self.patch(self.with_description(), {"title": "New"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["title"], body["description"]), ("New", "desc"))
        self.assertEqual(set(body), PROJECT_FIELDS)

    def test_leaving_out_the_title_keeps_it(self) -> None:
        body = self.patch(self.with_description(), {"description": "d2"}).json()
        self.assertEqual((body["title"], body["description"]), ("Old", "d2"))

    def test_null_description_clears_it(self) -> None:
        body = self.patch(self.with_description(), {"description": None}).json()
        self.assertEqual((body["title"], body["description"]), ("Old", None))

    def test_empty_description_clears_it(self) -> None:
        body = self.patch(self.with_description(), {"description": ""}).json()
        self.assertIsNone(body["description"])

    def test_empty_body_changes_nothing(self) -> None:
        body = self.patch(self.with_description(), {}).json()
        self.assertEqual((body["title"], body["description"]), ("Old", "desc"))

    def test_null_title_is_a_validation_error(self) -> None:
        response = self.patch(self.insert_project(), {"title": None})
        self.assert_field_error(response, "title")

    def test_bad_title_is_a_validation_error_and_changes_nothing(self) -> None:
        project_id = self.insert_project("Keep")
        self.assert_field_error(self.patch(project_id, {"title": " "}), "title")
        self.assert_field_error(self.patch(project_id, {"title": "x" * 256}), "title")
        rows = fetch("SELECT title FROM projects WHERE id = $1", project_id)
        self.assertEqual(rows[0]["title"], "Keep")

    def test_other_users_project_is_forbidden_and_unchanged(self) -> None:
        project_id = self.insert_project("Theirs", user_id=OTHER)
        self.assert_error(self.patch(project_id, {"title": "Hacked"}), 403, "forbidden")
        rows = fetch("SELECT title FROM projects WHERE id = $1", project_id)
        self.assertEqual(rows[0]["title"], "Theirs")

    def test_missing_project_is_404(self) -> None:
        self.assert_error(self.patch(uuid.uuid4(), {"title": "x"}), 404, "not_found")

    def test_non_uuid_id_is_a_validation_error_on_project_id(self) -> None:
        self.assert_field_error(self.patch("nope", {"title": "x"}), "project_id")


class TestDeleteProject(ProjectsApiTestCase):
    def delete(self, project_id: Any) -> Any:
        return self.client.delete(f"{BASE}/{project_id}", headers=auth())

    def test_requires_sign_in(self) -> None:
        self.assert_requires_sign_in("DELETE", f"{BASE}/{uuid.uuid4()}")

    def test_moves_the_project_to_the_trash(self) -> None:
        project_id = self.insert_project()
        response = self.delete(project_id)
        self.assertEqual((response.status_code, response.content), (204, b""))
        rows = fetch(
            "SELECT deletion_status, trashed_at FROM projects WHERE id = $1",
            project_id,
        )
        self.assertEqual(rows[0]["deletion_status"], "trashed")
        self.assertIsNotNone(rows[0]["trashed_at"])
        self.assert_error(
            self.client.get(f"{BASE}/{project_id}", headers=auth()), 404, "not_found"
        )

    def test_deleting_twice_is_404(self) -> None:
        project_id = self.insert_project()
        self.delete(project_id)
        self.assert_error(self.delete(project_id), 404, "not_found")

    def test_other_users_project_is_forbidden_and_stays_active(self) -> None:
        project_id = self.insert_project(user_id=OTHER)
        self.assert_error(self.delete(project_id), 403, "forbidden")
        rows = fetch("SELECT deletion_status FROM projects WHERE id = $1", project_id)
        self.assertEqual(rows[0]["deletion_status"], "active")

    def test_missing_project_is_404(self) -> None:
        self.assert_error(self.delete(uuid.uuid4()), 404, "not_found")

    def test_non_uuid_id_is_a_validation_error_on_project_id(self) -> None:
        self.assert_field_error(self.delete("nope"), "project_id")

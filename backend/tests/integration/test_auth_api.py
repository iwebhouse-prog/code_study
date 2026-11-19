"""Auth endpoints end to end against PostgreSQL (T028-T031)."""

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from src.api.dependencies import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.main import create_app
from src.utils.jwt import JWTConfig, create_access_token
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    execute_script,
    recreate_test_database,
    run_alembic,
)
from tests.unit.test_auth_api import parse_cookies

JWT_CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
BASE = "/api/v1/auth"
EMAIL = "learner@example.com"
PASSWORD = "learning123"
CREDENTIALS = {"email": EMAIL, "password": PASSWORD}
USER_FIELDS = {"id", "email", "skill_level", "created_at", "last_login_at"}


def make_client(environment: str = "development") -> TestClient:
    app = create_app(
        app_config=AppConfig(environment=environment),
        db_config=DatabaseConfig(url=TEST_DATABASE_URL),
        jwt_config=JWT_CONFIG,
    )
    client = TestClient(app)
    client.__enter__()
    return client


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class AuthApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def setUp(self) -> None:
        self.client = make_client()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.client.post(f"{BASE}{path}", json=body)

    def register(self) -> Any:
        return self.post("/register", CREDENTIALS)

    def assert_error(self, response: Any, status: int, error: str) -> None:
        self.assertEqual(response.status_code, status)
        body = response.json()
        self.assertEqual(body["error"], error)
        self.assertRegex(body["message"], "[가-힣]")

    def assert_cookies_cleared(self, response: Any) -> None:
        cookies = parse_cookies(response)
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["max-age"], "0")
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["path"], "/")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["max-age"], "0")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["path"], "/api/v1/auth")


class TestRegister(AuthApiTestCase):
    def test_creates_the_account_and_returns_the_user(self) -> None:
        response = self.register()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body), USER_FIELDS)
        self.assertEqual(body["email"], EMAIL)
        self.assertEqual(body["skill_level"], "Complete Beginner")
        self.assertIsNone(body["last_login_at"])
        self.assertNotIn("password", response.text)

    def test_signs_the_user_in_with_both_cookies(self) -> None:
        response = self.register()
        cookies = parse_cookies(response)
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["max-age"], "900")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["max-age"], "604800")
        me = self.client.get(f"{BASE}/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], EMAIL)

    def test_email_is_normalized(self) -> None:
        response = self.post(
            "/register", {"email": " Learner@Example.COM ", **{"password": PASSWORD}}
        )
        self.assertEqual(response.json()["email"], EMAIL)

    def test_duplicate_email_is_a_conflict(self) -> None:
        self.register()
        self.client.cookies.clear()
        response = self.register()
        self.assert_error(response, 409, "email_taken")
        self.assertNotIn("set-cookie", response.headers)

    def test_weak_password_names_the_password_field(self) -> None:
        response = self.post("/register", {"email": EMAIL, "password": "short1"})
        self.assert_error(response, 400, "validation_error")
        fields = response.json()["details"]["fields"]
        self.assertEqual([f["field"] for f in fields], ["password"])

    def test_invalid_email_names_the_email_field(self) -> None:
        response = self.post(
            "/register", {"email": "not-an-email", "password": PASSWORD}
        )
        self.assert_error(response, 400, "validation_error")
        fields = response.json()["details"]["fields"]
        self.assertEqual([f["field"] for f in fields], ["email"])

    def test_missing_fields_are_validation_errors(self) -> None:
        response = self.post("/register", {})
        self.assert_error(response, 400, "validation_error")
        fields = {f["field"] for f in response.json()["details"]["fields"]}
        self.assertEqual(fields, {"email", "password"})


class TestLogin(AuthApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.register()
        self.client.cookies.clear()

    def test_returns_the_user_and_sets_both_cookies(self) -> None:
        response = self.post("/login", CREDENTIALS)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), USER_FIELDS)
        self.assertIsNotNone(body["last_login_at"])
        cookies = parse_cookies(response)
        self.assertEqual(set(cookies), {ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE})
        self.assertEqual(self.client.get(f"{BASE}/me").status_code, 200)

    def test_wrong_password_and_unknown_email_look_the_same(self) -> None:
        wrong = self.post("/login", {"email": EMAIL, "password": "wrong-pass1"})
        unknown = self.post(
            "/login", {"email": "who@example.com", "password": PASSWORD}
        )
        self.assert_error(wrong, 401, "invalid_credentials")
        self.assert_error(unknown, 401, "invalid_credentials")
        self.assertEqual(wrong.json(), unknown.json())
        self.assertNotIn("set-cookie", wrong.headers)

    def test_missing_password_is_a_validation_error(self) -> None:
        response = self.post("/login", {"email": EMAIL})
        self.assert_error(response, 400, "validation_error")

    def test_empty_body_is_a_validation_error(self) -> None:
        response = self.client.post(f"{BASE}/login")
        self.assert_error(response, 400, "validation_error")


class TestMe(AuthApiTestCase):
    def test_returns_the_signed_in_user(self) -> None:
        self.register()
        response = self.client.get(f"{BASE}/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), USER_FIELDS)

    def test_without_cookie_is_unauthorized(self) -> None:
        self.assert_error(self.client.get(f"{BASE}/me"), 401, "unauthorized")

    def test_expired_access_token_asks_for_a_refresh(self) -> None:
        user_id = self.register().json()["id"]
        self.client.cookies.clear()
        past = datetime.now(UTC) - timedelta(minutes=16)
        from uuid import UUID

        token = create_access_token(UUID(user_id), JWT_CONFIG, now=past)
        response = self.client.get(
            f"{BASE}/me", headers={"Cookie": f"{ACCESS_TOKEN_COOKIE}={token}"}
        )
        self.assert_error(response, 401, "token_expired")


class TestLogout(AuthApiTestCase):
    def test_clears_both_cookies_with_no_body(self) -> None:
        self.register()
        response = self.post("/logout")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assert_cookies_cleared(response)

    def test_revokes_the_refresh_token(self) -> None:
        self.register()
        refresh = self.client.cookies.get(REFRESH_TOKEN_COOKIE, path=BASE)
        self.post("/logout")
        again = self.client.post(
            f"{BASE}/refresh",
            headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}={refresh}"},
        )
        self.assert_error(again, 401, "session_expired")

    def test_signed_out_user_cannot_read_me(self) -> None:
        self.register()
        self.post("/logout")
        self.assert_error(self.client.get(f"{BASE}/me"), 401, "unauthorized")

    def test_succeeds_without_any_cookie(self) -> None:
        response = self.post("/logout")
        self.assertEqual(response.status_code, 204)
        self.assert_cookies_cleared(response)

    def test_succeeds_with_a_garbage_cookie(self) -> None:
        response = self.client.post(
            f"{BASE}/logout", headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}=garbage"}
        )
        self.assertEqual(response.status_code, 204)

    def test_other_devices_stay_signed_in(self) -> None:
        self.register()
        device_a = self.client.cookies.get(REFRESH_TOKEN_COOKIE, path=BASE)
        self.client.cookies.clear()
        self.post("/login", CREDENTIALS)  # device B
        self.post("/logout")  # only B signs out
        self.client.cookies.clear()
        response = self.client.post(
            f"{BASE}/refresh", headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}={device_a}"}
        )
        self.assertEqual(response.status_code, 200)


class TestRefresh(AuthApiTestCase):
    def test_rotates_both_cookies_and_returns_the_user(self) -> None:
        self.register()
        old_refresh = self.client.cookies.get(REFRESH_TOKEN_COOKIE, path=BASE)
        response = self.post("/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), USER_FIELDS)
        cookies = parse_cookies(response)
        self.assertEqual(set(cookies), {ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE})
        self.assertNotEqual(cookies[REFRESH_TOKEN_COOKIE].value, old_refresh)
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["max-age"], "604800")
        self.assertEqual(self.client.get(f"{BASE}/me").status_code, 200)

    def test_reused_token_is_refused_and_clears_cookies(self) -> None:
        self.register()
        old_refresh = self.client.cookies.get(REFRESH_TOKEN_COOKIE, path=BASE)
        self.post("/refresh")
        self.client.cookies.clear()
        response = self.client.post(
            f"{BASE}/refresh",
            headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}={old_refresh}"},
        )
        self.assert_error(response, 401, "session_expired")
        self.assert_cookies_cleared(response)

    def test_missing_cookie_is_session_expired_and_clears_cookies(self) -> None:
        response = self.post("/refresh")
        self.assert_error(response, 401, "session_expired")
        self.assert_cookies_cleared(response)

    def test_garbage_cookie_is_session_expired_and_clears_cookies(self) -> None:
        response = self.client.post(
            f"{BASE}/refresh", headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}=garbage"}
        )
        self.assert_error(response, 401, "session_expired")
        self.assert_cookies_cleared(response)


class TestProductionCookies(AuthApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.__exit__(None, None, None)
        self.client = make_client("production")

    def test_cookies_are_secure_in_production(self) -> None:
        response = self.register()
        for cookie in parse_cookies(response).values():
            self.assertTrue(cookie["secure"])

    def test_cleared_cookies_stay_secure_in_production(self) -> None:
        response = self.post("/logout")
        for cookie in parse_cookies(response).values():
            self.assertTrue(cookie["secure"])

    def test_cookies_are_not_secure_in_development(self) -> None:
        self.client.__exit__(None, None, None)
        self.client = make_client("development")
        for cookie in parse_cookies(self.register()).values():
            self.assertFalse(cookie["secure"])


if __name__ == "__main__":
    unittest.main()

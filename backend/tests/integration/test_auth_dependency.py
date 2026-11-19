"""Protects a real route with CurrentUser against PostgreSQL (T027)."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.api.dependencies import ACCESS_TOKEN_COOKIE, CurrentUser
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.main import create_app
from src.utils.jwt import JWTConfig, create_access_token, create_refresh_token
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    execute_script,
    recreate_test_database,
    run_alembic,
)

JWT_CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
EMAIL = "learner@example.com"
URL = "/protected"


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestCurrentUser(unittest.TestCase):
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
            "INSERT INTO users (id, email, password_hash) "
            f"VALUES ('{USER_ID}', '{EMAIL}', 'hash')"
        )
        app = create_app(
            app_config=AppConfig(),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWT_CONFIG,
        )

        @app.get(URL)
        async def protected(user: CurrentUser) -> dict[str, str]:
            return {"email": user.email}

        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        execute_script("DELETE FROM users")

    def _get(self, token: str | None = None) -> tuple[int, dict[str, str]]:
        cookies = {ACCESS_TOKEN_COOKIE: token} if token is not None else {}
        response = self.client.get(URL, headers=_cookie_header(cookies))
        return response.status_code, response.json()

    def test_valid_cookie_reaches_the_route_with_the_user(self) -> None:
        token = create_access_token(USER_ID, JWT_CONFIG)
        self.assertEqual(self._get(token), (200, {"email": EMAIL}))

    def test_no_cookie_is_refused_in_the_shared_error_format(self) -> None:
        status, body = self._get()
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")
        self.assertIn("로그인", body["message"])

    def test_expired_token_tells_the_frontend_to_refresh(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=16)
        status, body = self._get(create_access_token(USER_ID, JWT_CONFIG, now=past))
        self.assertEqual((status, body["error"]), (401, "token_expired"))

    def test_forged_token_is_refused(self) -> None:
        forged = create_access_token(
            USER_ID, JWTConfig(access_secret="x" * 32, refresh_secret="y" * 32)
        )
        status, body = self._get(forged)
        self.assertEqual((status, body["error"]), (401, "session_expired"))

    def test_refresh_token_cannot_open_routes(self) -> None:
        status, body = self._get(create_refresh_token(USER_ID, JWT_CONFIG))
        self.assertEqual((status, body["error"]), (401, "session_expired"))

    def test_token_of_a_deleted_user_is_refused(self) -> None:
        token = create_access_token(USER_ID, JWT_CONFIG)
        execute_script("DELETE FROM users")
        status, body = self._get(token)
        self.assertEqual((status, body["error"]), (401, "session_expired"))

    def test_authorization_header_is_not_a_way_in(self) -> None:
        # Tokens live in HTTPOnly cookies only (research.md section 8).
        token = create_access_token(USER_ID, JWT_CONFIG)
        response = self.client.get(URL, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)


def _cookie_header(cookies: dict[str, str]) -> dict[str, str]:
    if not cookies:
        return {}
    return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}

"""Verifies FastAPI app startup, CORS, security headers and /health (T014)."""

import os
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src import config as app_config_module
from src import main
from src.config import AppConfig
from src.db.config import DatabaseConfig, DatabaseUnavailableError
from src.utils.jwt import JWTConfig

FRONTEND = "http://localhost:5173"
DB_CONFIG = DatabaseConfig(url="postgresql+asyncpg://u:p@127.0.0.1:5432/db")
JWT_CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)


def _fake_database() -> MagicMock:
    database = MagicMock()
    database.ping = AsyncMock()
    return database


@contextmanager
def running_app(
    app_config: AppConfig | None = None, database: MagicMock | None = None
) -> Iterator[tuple[TestClient, AsyncMock, MagicMock]]:
    database = database or _fake_database()
    connect = AsyncMock(return_value=database)
    app = main.create_app(
        app_config=app_config or AppConfig(allowed_origins=(FRONTEND,)),
        db_config=DB_CONFIG,
        jwt_config=JWT_CONFIG,
        connect=connect,
    )
    with (
        patch.object(main, "close_database", new=AsyncMock()) as close,
        TestClient(app) as client,
    ):
        yield client, connect, close
    close.assert_awaited_once()


class TestLifespan(unittest.TestCase):
    def test_connects_database_on_startup_and_closes_on_shutdown(self) -> None:
        with running_app() as (client, connect, _close):
            connect.assert_awaited_once_with(DB_CONFIG)
            self.assertIs(client.app.state.jwt_config, JWT_CONFIG)  # type: ignore[attr-defined]

    def test_startup_fails_when_database_is_unavailable(self) -> None:
        connect = AsyncMock(side_effect=DatabaseUnavailableError("down"))
        app = main.create_app(
            app_config=AppConfig(),
            db_config=DB_CONFIG,
            jwt_config=JWT_CONFIG,
            connect=connect,
        )
        with self.assertRaises(DatabaseUnavailableError), TestClient(app):
            pass


class TestCreateAppFromEnv(unittest.TestCase):
    def test_reads_all_settings_from_environment(self) -> None:
        env = {
            "DATABASE_URL": DB_CONFIG.url,
            "JWT_SECRET_KEY": "a" * 32,
            "JWT_REFRESH_SECRET": "r" * 32,
            "ALLOWED_ORIGINS": FRONTEND,
        }
        with (
            patch.object(app_config_module, "load_dotenv"),
            patch.dict(os.environ, env, clear=True),
        ):
            app = main.create_app()
        self.assertEqual(app.state.jwt_config.access_secret, "a" * 32)

    def test_bad_jwt_secret_stops_app_creation(self) -> None:
        # T012 promised that a placeholder secret is caught at server start.
        env = {
            "DATABASE_URL": DB_CONFIG.url,
            "JWT_SECRET_KEY": "change-me-access-token-secret",
            "JWT_REFRESH_SECRET": "r" * 32,
        }
        with (
            patch.object(app_config_module, "load_dotenv"),
            patch.dict(os.environ, env, clear=True),
            self.assertRaisesRegex(ValueError, "JWT_SECRET_KEY"),
        ):
            main.create_app()


class TestHealth(unittest.TestCase):
    def test_reports_ok_when_database_answers(self) -> None:
        with running_app() as (client, _connect, _close):
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_reports_503_when_database_stops_answering(self) -> None:
        database = _fake_database()
        database.ping.side_effect = OperationalError("SELECT 1", {}, Exception())
        with running_app(database=database) as (client, _connect, _close):
            response = client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"status": "unavailable", "database": "unavailable"}
        )


class TestCors(unittest.TestCase):
    def _preflight(self, client: TestClient, origin: str) -> dict[str, str]:
        response = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        return dict(response.headers)

    def test_allowed_origin_may_send_cookies(self) -> None:
        with running_app() as (client, _connect, _close):
            headers = self._preflight(client, FRONTEND)
        self.assertEqual(headers["access-control-allow-origin"], FRONTEND)
        self.assertEqual(headers["access-control-allow-credentials"], "true")

    def test_other_origin_is_not_allowed(self) -> None:
        with running_app() as (client, _connect, _close):
            headers = self._preflight(client, "http://evil.example")
            simple = client.get("/health", headers={"Origin": "http://evil.example"})
        self.assertNotIn("access-control-allow-origin", headers)
        self.assertNotIn("access-control-allow-origin", simple.headers)

    def test_simple_request_from_allowed_origin_gets_cors_header(self) -> None:
        with running_app() as (client, _connect, _close):
            response = client.get("/health", headers={"Origin": FRONTEND})
        self.assertEqual(response.headers["access-control-allow-origin"], FRONTEND)


class TestSecurityHeaders(unittest.TestCase):
    def test_every_response_has_security_headers(self) -> None:
        with running_app() as (client, _connect, _close):
            for path in ("/health", "/no-such-page"):
                with self.subTest(path=path):
                    headers = client.get(path).headers
                    self.assertEqual(headers["x-content-type-options"], "nosniff")
                    self.assertEqual(headers["x-frame-options"], "DENY")
                    self.assertEqual(
                        headers["referrer-policy"], "strict-origin-when-cross-origin"
                    )

    def test_hsts_only_in_production(self) -> None:
        with running_app() as (client, _connect, _close):
            self.assertNotIn("strict-transport-security", client.get("/health").headers)
        production = AppConfig(environment="production")
        with running_app(production) as (client, _connect, _close):
            self.assertEqual(
                client.get("/health").headers["strict-transport-security"],
                "max-age=31536000; includeSubDomains",
            )


class TestApiDocs(unittest.TestCase):
    def test_docs_available_in_development(self) -> None:
        with running_app() as (client, _connect, _close):
            self.assertEqual(client.get("/docs").status_code, 200)
            self.assertEqual(client.get("/openapi.json").status_code, 200)

    def test_docs_hidden_in_production(self) -> None:
        with running_app(AppConfig(environment="production")) as (
            client,
            _connect,
            _close,
        ):
            self.assertEqual(client.get("/docs").status_code, 404)
            self.assertEqual(client.get("/openapi.json").status_code, 404)

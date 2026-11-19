"""Starts the real app against PostgreSQL and checks /health (T014)."""

import unittest

from fastapi.testclient import TestClient

from src.config import AppConfig
from src.db import session as db_session
from src.db.config import DatabaseConfig
from src.main import create_app
from src.utils.jwt import JWTConfig
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestAppWithDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_health_checks_live_database_and_shutdown_closes_pool(self) -> None:
        app = create_app(
            app_config=AppConfig(),
            db_config=DatabaseConfig(url=TEST_DATABASE_URL),
            jwt_config=JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32),
        )
        with TestClient(app) as client:
            self.assertIs(app.state.database, db_session.get_database())
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
        with self.assertRaises(RuntimeError):
            db_session.get_database()

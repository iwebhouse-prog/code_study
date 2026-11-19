"""Verifies the /api/v1 router and how it is mounted on the app (T015)."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from fastapi.routing import APIRoute
from sqlalchemy.exc import OperationalError

from src.api.router import API_PREFIX, create_api_router
from tests.unit.test_main import FRONTEND, running_app


class TestApiRouter(unittest.TestCase):
    def test_prefix_matches_frontend_base_url(self) -> None:
        # frontend/.env.example: VITE_API_BASE_URL=http://localhost:8000/api/v1
        self.assertEqual(API_PREFIX, "/api/v1")

    def test_every_route_lives_under_prefix(self) -> None:
        routes = [r for r in create_api_router().routes if isinstance(r, APIRoute)]
        self.assertTrue(routes)
        for route in routes:
            with self.subTest(path=route.path):
                self.assertTrue(route.path.startswith(API_PREFIX))

    def test_each_call_builds_a_fresh_router(self) -> None:
        # Apps created in tests must not share (and pile up) routes.
        self.assertIsNot(create_api_router(), create_api_router())


class TestApiMountedOnApp(unittest.TestCase):
    def test_index_answers_with_api_version(self) -> None:
        with running_app() as (client, _connect, _close):
            response = client.get(API_PREFIX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"name": "AI Code Learning Platform API", "version": "v1"}
        )

    def test_index_is_listed_in_api_docs(self) -> None:
        with running_app() as (client, _connect, _close):
            paths = client.get("/openapi.json").json()["paths"]
        self.assertIn(API_PREFIX, paths)

    def test_unknown_api_path_is_404(self) -> None:
        with running_app() as (client, _connect, _close):
            self.assertEqual(client.get(f"{API_PREFIX}/nope").status_code, 404)

    def test_api_health_matches_root_health(self) -> None:
        # /health is for monitoring; /api/v1/health lets the frontend check the
        # API through the same base URL (and CORS) it uses for everything else.
        with running_app() as (client, _connect, _close):
            root = client.get("/health")
            api = client.get(f"{API_PREFIX}/health", headers={"Origin": FRONTEND})
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json(), {"status": "ok", "database": "ok"})
        self.assertEqual(api.json(), root.json())
        self.assertEqual(api.headers["access-control-allow-origin"], FRONTEND)

    def test_api_health_reports_503_when_database_is_down(self) -> None:
        database = MagicMock()
        database.ping = AsyncMock(
            side_effect=OperationalError("SELECT 1", {}, Exception())
        )
        with running_app(database=database) as (client, _connect, _close):
            response = client.get(f"{API_PREFIX}/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"status": "unavailable", "database": "unavailable"}
        )

    def test_api_health_is_listed_in_api_docs(self) -> None:
        with running_app() as (client, _connect, _close):
            paths = client.get("/openapi.json").json()["paths"]
        self.assertIn(f"{API_PREFIX}/health", paths)
        self.assertNotIn("/health", paths)

    def test_two_apps_do_not_share_routes(self) -> None:
        with running_app() as (first, _c1, _x1), running_app() as (second, _c2, _x2):
            count_first = len(first.app.routes)  # type: ignore[attr-defined]
            count_second = len(second.app.routes)  # type: ignore[attr-defined]
        self.assertEqual(count_first, count_second)

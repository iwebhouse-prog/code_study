"""Verifies the development-only /api/v1/test-errors endpoint."""

import unittest

from src.api.error_messages import ERROR_MESSAGES
from src.config import AppConfig
from tests.unit.test_main import running_app

URL = "/api/v1/test-errors"


class TestTestErrorsEndpoint(unittest.TestCase):
    def test_without_type_returns_success(self) -> None:
        with running_app() as (client, _connect, _close):
            response = client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "message": "오류 없음"})

    def test_each_type_raises_matching_error(self) -> None:
        cases = {"notfound": (404, "not_found"), "forbidden": (403, "forbidden")}
        cases["conflict"] = (409, "conflict")
        with running_app() as (client, _connect, _close):
            for kind, (status, error) in cases.items():
                with self.subTest(kind=kind):
                    response = client.get(URL, params={"type": kind})
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(
                        response.json(),
                        {"error": error, "message": ERROR_MESSAGES[error]},
                    )

    def test_unknown_type_is_validation_error(self) -> None:
        with running_app() as (client, _connect, _close):
            response = client.get(URL, params={"type": "boom"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "validation_error")
        self.assertEqual(response.json()["details"]["fields"][0]["field"], "type")

    def test_not_available_in_production(self) -> None:
        production = AppConfig(environment="production")
        with running_app(production) as (client, _connect, _close):
            self.assertEqual(client.get(URL).status_code, 404)

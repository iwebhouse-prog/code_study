"""Verifies the shared error response format and handlers (T016)."""

import unittest
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import OperationalError

from src import main
from src.api.error_messages import ERROR_MESSAGES
from src.api.exceptions import (
    AppError,
    ConflictError,
    ErrorResponse,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from src.config import AppConfig
from src.db.config import DatabaseConfig, DatabaseUnavailableError
from src.utils.jwt import JWTConfig

FRONTEND = "http://localhost:5173"


class SignUp(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(default="", max_length=10)

    @field_validator("nickname")
    @classmethod
    def no_admin(cls, value: str) -> str:
        if value == "admin":
            raise ValueError("사용할 수 없는 닉네임입니다.")
        return value


class FileTooLargeError(AppError):
    status_code = 413
    error = "file_too_large"
    message = "파일 크기가 10MB를 초과합니다."


def _add_test_routes(app: FastAPI) -> None:
    @app.get("/boom/not-found")
    async def not_found() -> None:
        raise NotFoundError(
            "요청한 프로젝트를 찾을 수 없습니다.",
            details={"project_id": "p1"},
            suggestion="프로젝트 목록에서 다시 선택하세요.",
        )

    @app.get("/boom/default/{kind}")
    async def default(kind: str) -> None:
        errors: dict[str, type[AppError]] = {
            "unauthorized": UnauthorizedError,
            "forbidden": ForbiddenError,
            "conflict": ConflictError,
        }
        raise errors[kind]()

    @app.get("/boom/custom")
    async def custom() -> None:
        raise FileTooLargeError(details={"max_size_mb": 10})

    @app.get("/boom/rate-limit")
    async def rate_limit() -> None:
        raise RateLimitError(retry_after=480)

    @app.get("/boom/http/{status}")
    async def http_error(status: int) -> None:
        raise HTTPException(status, "English detail", {"WWW-Authenticate": "Bearer"})

    @app.get("/boom/crash")
    async def crash() -> None:
        raise RuntimeError("secret internal detail: password=hunter2")

    @app.get("/boom/db-down")
    async def db_down() -> None:
        raise DatabaseUnavailableError("could not connect to 127.0.0.1:5432")

    @app.get("/boom/db-error")
    async def db_error() -> None:
        raise OperationalError("SELECT 1", {}, Exception("ECONNREFUSED"))

    @app.post("/boom/signup")
    async def signup(body: SignUp) -> dict[str, str]:
        return {"email": body.email}

    @app.get("/boom/stream")
    async def stream() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"first chunk"
            raise RuntimeError("failed mid-stream")

        return StreamingResponse(chunks())

    @app.get("/boom/page")
    async def page(size: int = 10) -> dict[str, int]:
        return {"size": size}


@contextmanager
def error_client(debug: bool = False) -> Iterator[TestClient]:
    database = MagicMock()
    database.ping = AsyncMock()
    app = main.create_app(
        app_config=AppConfig(debug=debug, allowed_origins=(FRONTEND,)),
        db_config=DatabaseConfig(url="postgresql+asyncpg://u:p@127.0.0.1/db"),
        jwt_config=JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32),
        connect=AsyncMock(return_value=database),
    )
    _add_test_routes(app)
    with (
        patch.object(main, "close_database", new=AsyncMock()),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        yield client


class TestErrorResponseSchema(unittest.TestCase):
    def test_optional_fields_are_left_out(self) -> None:
        body = ErrorResponse(error="not_found", message="없음").model_dump(
            exclude_none=True
        )
        self.assertEqual(body, {"error": "not_found", "message": "없음"})

    def test_every_message_is_korean(self) -> None:
        # CHK084: all user-facing messages are Korean.
        for code, message in ERROR_MESSAGES.items():
            with self.subTest(code=code):
                self.assertRegex(message, "[가-힣]")


class TestAppErrors(unittest.TestCase):
    def test_app_error_uses_shared_format(self) -> None:
        with error_client() as client:
            response = client.get("/boom/not-found")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "error": "not_found",
                "message": "요청한 프로젝트를 찾을 수 없습니다.",
                "details": {"project_id": "p1"},
                "suggestion": "프로젝트 목록에서 다시 선택하세요.",
            },
        )

    def test_default_messages_come_from_dictionary(self) -> None:
        cases = {"unauthorized": 401, "forbidden": 403, "conflict": 409}
        with error_client() as client:
            for kind, status in cases.items():
                with self.subTest(kind=kind):
                    response = client.get(f"/boom/default/{kind}")
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(
                        response.json(),
                        {"error": kind, "message": ERROR_MESSAGES[kind]},
                    )

    def test_subclass_can_define_its_own_error(self) -> None:
        with error_client() as client:
            response = client.get("/boom/custom")
        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json(),
            {
                "error": "file_too_large",
                "message": "파일 크기가 10MB를 초과합니다.",
                "details": {"max_size_mb": 10},
            },
        )

    def test_rate_limit_sets_retry_after(self) -> None:
        with error_client() as client:
            response = client.get("/boom/rate-limit")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "480")
        self.assertEqual(response.json()["error"], "rate_limit_exceeded")
        self.assertEqual(response.json()["details"], {"retry_after": 480})
        self.assertIn("8분", response.json()["message"])


class TestFrameworkErrors(unittest.TestCase):
    def test_unknown_path_is_korean_404(self) -> None:
        with error_client() as client:
            response = client.get("/api/v1/no-such-thing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"error": "not_found", "message": ERROR_MESSAGES["not_found"]},
        )

    def test_wrong_method_keeps_allow_header(self) -> None:
        with error_client() as client:
            response = client.delete("/api/v1")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"], "method_not_allowed")
        self.assertIn("GET", response.headers["allow"])

    def test_http_exception_gets_korean_message_and_keeps_headers(self) -> None:
        with error_client() as client:
            response = client.get("/boom/http/401")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"error": "unauthorized", "message": ERROR_MESSAGES["unauthorized"]},
        )
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_unlisted_4xx_status_is_bad_request(self) -> None:
        with error_client() as client:
            response = client.get("/boom/http/418")
        self.assertEqual(response.status_code, 418)
        self.assertEqual(response.json()["error"], "bad_request")


class TestValidationErrors(unittest.TestCase):
    def _fields(self, response_json: dict[str, object]) -> dict[str, str]:
        details = response_json["details"]
        assert isinstance(details, dict)
        return {item["field"]: item["message"] for item in details["fields"]}

    def test_validation_error_is_400_with_field_messages(self) -> None:
        # CHK084 lists validation errors under 400 (not FastAPI's default 422).
        with error_client() as client:
            response = client.post("/boom/signup", json={"password": "short"})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"], "validation_error")
        self.assertEqual(body["message"], ERROR_MESSAGES["validation_error"])
        self.assertEqual(
            self._fields(body),
            {"email": "필수 입력 항목입니다.", "password": "최소 8자 이상 입력하세요."},
        )

    def test_rejected_input_is_never_echoed(self) -> None:
        # FastAPI's default 422 body repeats the input, which may be a password.
        with error_client() as client:
            response = client.post(
                "/boom/signup", json={"email": "a@b.c", "password": "pw-secret"[:5]}
            )
        self.assertNotIn("pw-se", response.text)

    def test_max_length_message(self) -> None:
        with error_client() as client:
            response = client.post(
                "/boom/signup",
                json={"email": "a@b.c", "password": "x" * 8, "nickname": "n" * 11},
            )
        self.assertEqual(
            self._fields(response.json()),
            {"nickname": "최대 10자까지 입력할 수 있습니다."},
        )

    def test_custom_validator_message_is_used(self) -> None:
        with error_client() as client:
            response = client.post(
                "/boom/signup",
                json={"email": "a@b.c", "password": "x" * 8, "nickname": "admin"},
            )
        self.assertEqual(
            self._fields(response.json()), {"nickname": "사용할 수 없는 닉네임입니다."}
        )

    def test_wrong_type_in_query(self) -> None:
        with error_client() as client:
            response = client.get("/boom/page", params={"size": "ten"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self._fields(response.json()), {"size": "올바른 형식이 아닙니다."}
        )

    def test_broken_json_body(self) -> None:
        with error_client() as client:
            response = client.post(
                "/boom/signup",
                content=b"{not json",
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            list(self._fields(response.json()).values()),
            ["요청 본문이 올바른 JSON 형식이 아닙니다."],
        )


class TestServerErrors(unittest.TestCase):
    def test_crash_is_500_without_internal_details(self) -> None:
        with (
            error_client() as client,
            self.assertLogs("src.api.exceptions", "ERROR") as logs,
        ):
            response = client.get("/boom/crash", headers={"Origin": FRONTEND})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"error": "internal_error", "message": ERROR_MESSAGES["internal_error"]},
        )
        self.assertNotIn("hunter2", response.text)
        # The full traceback goes to the server log for developers.
        self.assertIn("RuntimeError", "\n".join(logs.output))

    def test_crash_response_keeps_cors_and_security_headers(self) -> None:
        # Otherwise the browser reports a CORS error instead of the real 500.
        with error_client() as client, self.assertLogs("src.api.exceptions"):
            response = client.get("/boom/crash", headers={"Origin": FRONTEND})
        self.assertEqual(response.headers["access-control-allow-origin"], FRONTEND)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_crash_is_json_even_in_debug_mode(self) -> None:
        with error_client(debug=True) as client, self.assertLogs("src.api.exceptions"):
            response = client.get("/boom/crash")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "internal_error")

    def test_database_unavailable_is_503(self) -> None:
        with error_client() as client:
            for path in ("/boom/db-down", "/boom/db-error"):
                with self.subTest(path=path), self.assertLogs("src.api.exceptions"):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(
                        response.json(),
                        {
                            "error": "service_unavailable",
                            "message": ERROR_MESSAGES["service_unavailable"],
                        },
                    )
                    self.assertNotIn("5432", response.text)
                    self.assertNotIn("ECONNREFUSED", response.text)

    def test_error_after_response_started_is_not_rewritten(self) -> None:
        # Status and headers are already sent, so a 500 body cannot follow.
        with (
            error_client() as client,
            self.assertLogs("src.api.exceptions", "ERROR") as logs,
        ):
            response = client.get("/boom/stream")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("internal_error", response.text)
        self.assertIn("failed mid-stream", "".join(logs.output))

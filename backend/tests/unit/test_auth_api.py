"""Cookie helpers, response schema and routes of the auth API (T028-T031)."""

import unittest
import uuid
from datetime import timedelta
from http.cookies import Morsel, SimpleCookie
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from src.api.auth import (
    AUTH_COOKIE_PATH,
    UserResponse,
    clear_auth_cookies,
    set_auth_cookies,
)
from src.api.dependencies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    get_token_service,
    get_user_service,
)
from src.api.router import API_PREFIX, create_api_router
from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.main import create_app
from src.services.auth.token_service import TokenPair
from src.utils.jwt import JWTConfig, create_access_token, create_refresh_token

JWT_CONFIG = JWTConfig(access_secret="a" * 32, refresh_secret="r" * 32)
PAIR = TokenPair(access_token="access-value", refresh_token="refresh-value")


def parse_cookies(response: Any) -> dict[str, Morsel[str]]:
    """Works for a Starlette response and an httpx response alike."""
    cookies: dict[str, Morsel[str]] = {}
    for name, value in response.headers.raw:
        if name.lower() != b"set-cookie":
            continue
        jar: SimpleCookie = SimpleCookie()
        jar.load(value.decode("latin-1"))
        cookies.update(jar)
    return cookies


class TestCookieNames(unittest.TestCase):
    def test_names_match_the_contract(self) -> None:
        self.assertEqual(ACCESS_TOKEN_COOKIE, "access_token")
        self.assertEqual(REFRESH_TOKEN_COOKIE, "refresh_token")

    def test_refresh_cookie_path_is_the_auth_prefix(self) -> None:
        self.assertEqual(AUTH_COOKIE_PATH, f"{API_PREFIX}/auth")


class TestSetAuthCookies(unittest.TestCase):
    def _cookies(self, secure: bool) -> dict[str, Morsel[str]]:
        response = Response()
        set_auth_cookies(response, PAIR, JWT_CONFIG, secure=secure)
        return parse_cookies(response)

    def test_access_cookie_follows_the_contract(self) -> None:
        cookie = self._cookies(secure=False)[ACCESS_TOKEN_COOKIE]
        self.assertEqual(cookie.value, "access-value")
        self.assertEqual(cookie["path"], "/")
        self.assertEqual(cookie["max-age"], "900")
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertTrue(cookie["httponly"])

    def test_refresh_cookie_follows_the_contract(self) -> None:
        cookie = self._cookies(secure=False)[REFRESH_TOKEN_COOKIE]
        self.assertEqual(cookie.value, "refresh-value")
        self.assertEqual(cookie["path"], "/api/v1/auth")
        self.assertEqual(cookie["max-age"], "604800")
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertTrue(cookie["httponly"])

    def test_max_age_follows_the_configured_lifetimes(self) -> None:
        config = JWTConfig(
            access_secret="a" * 32,
            refresh_secret="r" * 32,
            access_token_expire=timedelta(minutes=5),
            refresh_token_expire=timedelta(days=1),
        )
        response = Response()
        set_auth_cookies(response, PAIR, config, secure=False)
        cookies = parse_cookies(response)
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["max-age"], "300")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["max-age"], "86400")

    def test_secure_flag_only_when_asked(self) -> None:
        for secure in (True, False):
            for name, cookie in self._cookies(secure).items():
                with self.subTest(name=name, secure=secure):
                    self.assertEqual(bool(cookie["secure"]), secure)


class TestClearAuthCookies(unittest.TestCase):
    def test_both_cookies_expire_on_their_original_paths(self) -> None:
        response = Response()
        clear_auth_cookies(response, secure=True)
        cookies = parse_cookies(response)
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["path"], "/")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["path"], "/api/v1/auth")
        for cookie in cookies.values():
            self.assertEqual(cookie.value, "")
            self.assertEqual(cookie["max-age"], "0")
            self.assertTrue(cookie["httponly"])
            self.assertEqual(cookie["samesite"], "Strict")
            self.assertTrue(cookie["secure"])


class TestUserResponse(unittest.TestCase):
    def test_exposes_only_the_contract_fields(self) -> None:
        self.assertEqual(
            set(UserResponse.model_fields),
            {"id", "email", "skill_level", "created_at", "last_login_at"},
        )


class TestRoutes(unittest.TestCase):
    def test_auth_routes_are_mounted(self) -> None:
        # This FastAPI nests included routers, so read the flattened OpenAPI paths.
        app = FastAPI()
        app.include_router(create_api_router())
        paths = app.openapi()["paths"]
        for method, path in [
            ("post", "/register"),
            ("post", "/login"),
            ("get", "/me"),
            ("post", "/logout"),
            ("post", "/refresh"),
        ]:
            with self.subTest(path=path):
                self.assertIn(method, paths.get(f"{API_PREFIX}/auth{path}", {}))


class TestRefreshForVanishedUser(unittest.TestCase):
    def test_user_deleted_after_rotation_ends_the_session(self) -> None:
        # Cannot happen through the database (tokens cascade with the user),
        # but the route must still answer safely if the lookup finds nothing.
        user_id = uuid.uuid4()
        token_service = MagicMock()
        token_service.rotate = AsyncMock(
            return_value=TokenPair(
                create_access_token(user_id, JWT_CONFIG),
                create_refresh_token(user_id, JWT_CONFIG),
            )
        )
        token_service.verify_access_token = MagicMock(return_value=user_id)
        user_service = MagicMock()
        user_service.get_by_id = AsyncMock(return_value=None)

        app = create_app(
            app_config=AppConfig(),
            db_config=DatabaseConfig(url="postgresql+asyncpg://x:y@127.0.0.1:1/z"),
            jwt_config=JWT_CONFIG,
            connect=AsyncMock(return_value=MagicMock()),
        )
        app.dependency_overrides[get_token_service] = lambda: token_service
        app.dependency_overrides[get_user_service] = lambda: user_service
        with TestClient(app) as client:
            response = client.post(
                f"{API_PREFIX}/auth/refresh",
                headers={"Cookie": f"{REFRESH_TOKEN_COOKIE}=whatever"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "session_expired")
        cookies = parse_cookies(response)
        self.assertEqual(cookies[ACCESS_TOKEN_COOKIE]["max-age"], "0")
        self.assertEqual(cookies[REFRESH_TOKEN_COOKIE]["max-age"], "0")


if __name__ == "__main__":
    unittest.main()

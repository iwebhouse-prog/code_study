"""Verifies app settings: environment, debug flag and CORS origins (T014)."""

import os
import unittest
from unittest.mock import patch

from src import config as app_config_module
from src.config import AppConfig, load_env


class TestAppConfigFromEnv(unittest.TestCase):
    def test_defaults_are_safe(self) -> None:
        config = AppConfig.from_env({})
        self.assertEqual(config.environment, "development")
        self.assertFalse(config.debug)
        self.assertEqual(config.allowed_origins, ())

    def test_reads_comma_separated_origins(self) -> None:
        config = AppConfig.from_env(
            {"ALLOWED_ORIGINS": " http://localhost:5173 , ,http://127.0.0.1:5173"}
        )
        self.assertEqual(
            config.allowed_origins,
            ("http://localhost:5173", "http://127.0.0.1:5173"),
        )

    def test_wildcard_origin_is_rejected(self) -> None:
        # Auth uses cookies, and browsers refuse credentials with "*".
        with self.assertRaisesRegex(ValueError, r"ALLOWED_ORIGINS.*\*"):
            AppConfig.from_env({"ALLOWED_ORIGINS": "*"})

    def test_origin_with_path_or_trailing_slash_is_rejected(self) -> None:
        # Browsers send "http://localhost:5173" with no slash, so these never match.
        for origin in ("http://localhost:5173/", "http://localhost:5173/app"):
            with (
                self.subTest(origin=origin),
                self.assertRaisesRegex(ValueError, "ALLOWED_ORIGINS"),
            ):
                AppConfig.from_env({"ALLOWED_ORIGINS": origin})

    def test_origin_without_http_scheme_is_rejected(self) -> None:
        for origin in ("localhost:5173", "ftp://example.com"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                AppConfig.from_env({"ALLOWED_ORIGINS": origin})

    def test_production_requires_https_origins(self) -> None:
        with self.assertRaisesRegex(ValueError, "https"):
            AppConfig.from_env(
                {"ENVIRONMENT": "production", "ALLOWED_ORIGINS": "http://app.com"}
            )
        config = AppConfig.from_env(
            {"ENVIRONMENT": "production", "ALLOWED_ORIGINS": "https://app.com"}
        )
        self.assertEqual(config.allowed_origins, ("https://app.com",))

    def test_unknown_environment_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ENVIRONMENT"):
            AppConfig.from_env({"ENVIRONMENT": "prod"})

    def test_debug_flag_parsing(self) -> None:
        for raw, expected in (("true", True), ("1", True), ("FALSE", False)):
            with self.subTest(raw=raw):
                self.assertIs(AppConfig.from_env({"DEBUG": raw}).debug, expected)

    def test_invalid_debug_flag_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "DEBUG"):
            AppConfig.from_env({"DEBUG": "maybe"})

    def test_debug_is_not_allowed_in_production(self) -> None:
        # Debug mode shows stack traces to anyone calling the API.
        with self.assertRaisesRegex(ValueError, "DEBUG"):
            AppConfig.from_env({"ENVIRONMENT": "production", "DEBUG": "true"})

    def test_is_production(self) -> None:
        self.assertTrue(AppConfig(environment="production").is_production)
        self.assertFalse(AppConfig(environment="development").is_production)


class TestLoadEnv(unittest.TestCase):
    def test_given_mapping_is_used_as_is(self) -> None:
        env = {"A": "1"}
        with patch.object(app_config_module, "load_dotenv") as load_dotenv:
            self.assertIs(load_env(env), env)
        load_dotenv.assert_not_called()

    def test_reads_dotenv_without_overriding_real_variables(self) -> None:
        with patch.object(app_config_module, "load_dotenv") as load_dotenv:
            self.assertIs(load_env(None), os.environ)
        load_dotenv.assert_called_once()
        self.assertFalse(load_dotenv.call_args.kwargs["override"])

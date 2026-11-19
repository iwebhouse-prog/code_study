"""Verifies env templates list every setting and hold no real secrets (T005)."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ENV_EXAMPLE = REPO_ROOT / ".env.example"
FRONTEND_ENV_EXAMPLE = REPO_ROOT / "frontend" / ".env.example"

BACKEND_KEYS = [
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "DATABASE_URL",
    "REDIS_URL",
    "GOOGLE_API_KEY",
    "GEMINI_MODEL",
    "JWT_SECRET_KEY",
    "JWT_REFRESH_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "ENVIRONMENT",
    "DEBUG",
    "ALLOWED_ORIGINS",
    "UPLOAD_DIR",
    "MAX_UPLOAD_SIZE_MB",
]

FRONTEND_KEYS = ["VITE_API_BASE_URL", "VITE_ENVIRONMENT"]

SECRET_KEYS = ["GOOGLE_API_KEY", "JWT_SECRET_KEY", "JWT_REFRESH_SECRET"]


def parse_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


class TestBackendEnvExample(unittest.TestCase):
    def test_lists_every_backend_setting(self) -> None:
        missing = [k for k in BACKEND_KEYS if k not in parse_env(BACKEND_ENV_EXAMPLE)]
        self.assertEqual(missing, [], f"Missing keys: {missing}")

    def test_secrets_are_placeholders(self) -> None:
        env = parse_env(BACKEND_ENV_EXAMPLE)
        for key in SECRET_KEYS:
            self.assertTrue(
                env[key].startswith("change-me"), f"{key} must be a placeholder"
            )

    def test_database_url_matches_postgres_settings(self) -> None:
        env = parse_env(BACKEND_ENV_EXAMPLE)
        expected = (
            f"postgresql+asyncpg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
            f"@127.0.0.1:5432/{env['POSTGRES_DB']}"
        )
        self.assertEqual(env["DATABASE_URL"], expected)

    def test_token_lifetimes_follow_research(self) -> None:
        env = parse_env(BACKEND_ENV_EXAMPLE)
        self.assertEqual(env["ACCESS_TOKEN_EXPIRE_MINUTES"], "15")
        self.assertEqual(env["REFRESH_TOKEN_EXPIRE_DAYS"], "7")

    def test_gemini_model_follows_plan(self) -> None:
        self.assertEqual(
            parse_env(BACKEND_ENV_EXAMPLE)["GEMINI_MODEL"], "gemini-3-flash-preview"
        )


class TestFrontendEnvExample(unittest.TestCase):
    def test_lists_every_frontend_setting(self) -> None:
        missing = [k for k in FRONTEND_KEYS if k not in parse_env(FRONTEND_ENV_EXAMPLE)]
        self.assertEqual(missing, [], f"Missing keys: {missing}")

    def test_api_base_url_points_to_v1(self) -> None:
        url = parse_env(FRONTEND_ENV_EXAMPLE)["VITE_API_BASE_URL"]
        self.assertEqual(url, "http://localhost:8000/api/v1")


if __name__ == "__main__":
    unittest.main()

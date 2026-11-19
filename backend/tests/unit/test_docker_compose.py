"""Verifies docker-compose.yml provides PostgreSQL and Redis for local dev (T004)."""

import unittest
from pathlib import Path

import yaml

COMPOSE_FILE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def load_services() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]


class TestDockerCompose(unittest.TestCase):
    def test_compose_file_exists(self) -> None:
        self.assertTrue(COMPOSE_FILE.is_file())

    def test_postgres_service(self) -> None:
        db = load_services()["db"]
        image, tag = db["image"].split(":")
        self.assertEqual(image, "postgres")
        self.assertGreaterEqual(int(tag.split(".")[0].split("-")[0]), 15)
        self.assertIn("127.0.0.1:5432:5432", db["ports"])
        self.assertIn("pg_isready", " ".join(db["healthcheck"]["test"]))

    def test_postgres_credentials_come_from_env(self) -> None:
        env = load_services()["db"]["environment"]
        for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
            self.assertTrue(env[key].startswith("${"), f"{key} must be read from .env")

    def test_postgres_data_persists_in_volume(self) -> None:
        volumes = load_services()["db"]["volumes"]
        self.assertIn("postgres_data:/var/lib/postgresql/data", volumes)

    def test_redis_service(self) -> None:
        redis = load_services()["redis"]
        self.assertTrue(redis["image"].startswith("redis:"))
        self.assertIn("127.0.0.1:6379:6379", redis["ports"])
        self.assertIn("ping", " ".join(redis["healthcheck"]["test"]))


if __name__ == "__main__":
    unittest.main()

"""Runs Alembic against the real PostgreSQL from docker-compose (T008).

Skipped when the database is not reachable (e.g. `docker compose up -d` not run).
"""

import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/codelearning"


def database_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


def run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestAlembicMigrations(unittest.TestCase):
    def test_upgrade_head_succeeds(self) -> None:
        result = run_alembic("upgrade", "head", database_url=DEFAULT_URL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_current_connects_to_database(self) -> None:
        result = run_alembic("current", database_url=DEFAULT_URL)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_environment_variable_overrides_dotenv(self) -> None:
        bad_url = "postgresql+asyncpg://nobody:wrong@127.0.0.1:5432/missing_db"
        result = run_alembic("current", database_url=bad_url)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

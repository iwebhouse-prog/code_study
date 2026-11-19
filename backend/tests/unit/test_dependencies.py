"""Verifies requirements.txt installs every library the plan relies on (T002)."""

import importlib
import unittest
from pathlib import Path

REQUIREMENTS_FILE = Path(__file__).resolve().parents[2] / "requirements.txt"

REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "dotenv",
    "pydantic",
    "jwt",
    "bcrypt",
    "python_multipart",
    "httpx",
    "google.genai",
    "celery",
    "redis",
    "pygments",
    "pytest",
    "pytest_asyncio",
    "pytest_cov",
]


class TestDependencies(unittest.TestCase):
    def test_requirements_file_exists(self) -> None:
        self.assertTrue(REQUIREMENTS_FILE.is_file())

    def test_every_requirement_is_pinned(self) -> None:
        lines = [
            line.strip()
            for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        unpinned = [line for line in lines if "==" not in line]
        self.assertEqual(unpinned, [], f"Unpinned requirements: {unpinned}")

    def test_required_modules_importable(self) -> None:
        missing = []
        for module in REQUIRED_MODULES:
            try:
                importlib.import_module(module)
            except ImportError:
                missing.append(module)
        self.assertEqual(missing, [], f"Missing modules: {missing}")

    def test_bcrypt_hashes_and_verifies(self) -> None:
        import bcrypt

        hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt(rounds=4))
        self.assertTrue(bcrypt.checkpw(b"password123", hashed))


if __name__ == "__main__":
    unittest.main()

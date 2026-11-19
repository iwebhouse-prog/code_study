"""Verifies the Alembic migration framework is configured (T008)."""

import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def load_config() -> Config:
    return Config(str(ALEMBIC_INI))


class TestAlembicSetup(unittest.TestCase):
    def test_script_location_is_backend_alembic(self) -> None:
        script = ScriptDirectory.from_config(load_config())
        self.assertEqual(Path(script.dir).resolve(), BACKEND_DIR / "alembic")

    def test_versions_directory_exists(self) -> None:
        self.assertTrue((BACKEND_DIR / "alembic" / "versions").is_dir())

    def test_env_script_exists(self) -> None:
        self.assertTrue((BACKEND_DIR / "alembic" / "env.py").is_file())

    def test_no_database_url_in_ini(self) -> None:
        self.assertIsNone(load_config().get_main_option("sqlalchemy.url"))

    def test_revision_files_are_numbered(self) -> None:
        template = load_config().get_main_option("file_template")
        self.assertEqual(template, "%(rev)s_%(slug)s")


if __name__ == "__main__":
    unittest.main()

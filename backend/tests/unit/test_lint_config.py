"""Verifies linting/formatting is configured and the codebase passes it (T006)."""

import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )


class TestPythonTooling(unittest.TestCase):
    def test_pyproject_configures_ruff_black_mypy(self) -> None:
        pyproject = (BACKEND_DIR / "pyproject.toml").read_text("utf-8")
        tool = tomllib.loads(pyproject)["tool"]
        self.assertEqual(tool["ruff"]["line-length"], tool["black"]["line-length"])
        self.assertTrue(tool["mypy"]["strict"])

    def test_ruff_passes(self) -> None:
        result = run_tool("ruff", "check", "src", "tests", "alembic")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_black_passes(self) -> None:
        result = run_tool("black", "--check", "src", "tests", "alembic")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mypy_strict_passes(self) -> None:
        result = run_tool("mypy", "src")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestFrontendTooling(unittest.TestCase):
    def test_config_files_exist(self) -> None:
        for name in ("eslint.config.js", ".prettierrc.json", ".prettierignore"):
            self.assertTrue((FRONTEND_DIR / name).is_file(), f"Missing {name}")

    def test_package_scripts(self) -> None:
        package_json = (FRONTEND_DIR / "package.json").read_text("utf-8")
        scripts = json.loads(package_json)["scripts"]
        for name in ("lint", "format", "format:check"):
            self.assertIn(name, scripts)


if __name__ == "__main__":
    unittest.main()

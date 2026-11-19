"""Verifies .gitignore keeps secrets, deps and build output out of Git (T007)."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IGNORE_FILES = [".gitignore", "frontend/.gitignore"]
GIT = shutil.which("git") or "git"

MUST_IGNORE = [
    ".env",
    "backend/.env",
    "frontend/.env.local",
    "backend/.venv/Scripts/python.exe",
    "backend/venv/Scripts/python.exe",
    "frontend/node_modules/react/index.js",
    "frontend/dist/index.html",
    "frontend/coverage/index.html",
    "backend/htmlcov/index.html",
    "backend/.coverage",
    "backend/src/__pycache__/main.cpython-312.pyc",
    "backend/.pytest_cache/README.md",
    "backend/.ruff_cache/CACHEDIR.TAG",
    "backend/.mypy_cache/CACHEDIR.TAG",
    "storage/uploads/1/2/main.py",
    ".claude/settings.local.json",
    ".vscode/launch.json",
    "npm-debug.log",
    "Thumbs.db",
    ".DS_Store",
    ".idea/workspace.xml",
]

MUST_TRACK = [
    ".env.example",
    "frontend/.env.example",
    "storage/uploads/.gitkeep",
    ".vscode/settings.json",
    ".vscode/extensions.json",
    ".claude/commands/speckit.implement.md",
    "backend/requirements.txt",
    "backend/src/__init__.py",
    "frontend/package-lock.json",
    "docker-compose.yml",
    "docs/task-reports/TASK-001-프로젝트-디렉토리-구조-생성.md",
]


class TestGitignore(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sandbox = Path(tempfile.mkdtemp())
        subprocess.run([GIT, "init", "-q"], cwd=cls.sandbox, check=True)
        for relative in IGNORE_FILES:
            target = cls.sandbox / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO_ROOT / relative, target)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.sandbox, ignore_errors=True)

    def is_ignored(self, path: str) -> bool:
        result = subprocess.run(
            [GIT, "-c", "core.quotepath=off", "check-ignore", "--no-index", path],
            cwd=self.sandbox,
            capture_output=True,
        )
        return result.returncode == 0

    def test_root_gitignore_exists(self) -> None:
        self.assertTrue((REPO_ROOT / ".gitignore").is_file())

    def test_sensitive_and_generated_files_are_ignored(self) -> None:
        not_ignored = [p for p in MUST_IGNORE if not self.is_ignored(p)]
        self.assertEqual(not_ignored, [], f"Should be ignored: {not_ignored}")

    def test_project_files_are_tracked(self) -> None:
        ignored = [p for p in MUST_TRACK if self.is_ignored(p)]
        self.assertEqual(ignored, [], f"Should be tracked: {ignored}")


if __name__ == "__main__":
    unittest.main()

"""Verifies the repo layout from plan.md (T001) and constitution II (T001A)."""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

BACKEND_PACKAGES = [
    "backend/src",
    "backend/src/models",
    "backend/src/api",
    "backend/src/db",
    "backend/src/utils",
    "backend/src/tasks",
    "backend/src/services",
    "backend/src/services/auth",
    "backend/src/services/code_analysis",
    "backend/src/services/ai",
    "backend/src/services/document",
    "backend/src/services/practice",
    "backend/src/services/qa",
    "backend/src/services/progress",
    "backend/tests",
    "backend/tests/contract",
    "backend/tests/integration",
    "backend/tests/unit",
]

FRONTEND_DIRS = [
    "frontend/src/components/auth",
    "frontend/src/components/project",
    "frontend/src/components/task",
    "frontend/src/components/upload",
    "frontend/src/components/document",
    "frontend/src/components/practice",
    "frontend/src/components/qa",
    "frontend/src/components/progress",
    "frontend/src/components/trash",
    "frontend/src/pages",
    "frontend/src/services",
    "frontend/src/hooks",
    "frontend/src/stores",
    "frontend/src/lib",
    "frontend/src/utils",
    "frontend/tests/integration",
    "frontend/tests/unit",
]

STORAGE_DIRS = ["storage/uploads"]


class TestProjectStructure(unittest.TestCase):
    def assert_dirs_exist(self, relative_dirs: list[str]) -> None:
        missing = [d for d in relative_dirs if not (REPO_ROOT / d).is_dir()]
        self.assertEqual(missing, [], f"Missing directories: {missing}")

    def test_backend_packages_exist(self) -> None:
        self.assert_dirs_exist(BACKEND_PACKAGES)

    def test_backend_packages_are_importable(self) -> None:
        missing = [
            d for d in BACKEND_PACKAGES if not (REPO_ROOT / d / "__init__.py").is_file()
        ]
        self.assertEqual(missing, [], f"Missing __init__.py: {missing}")

    def test_frontend_dirs_exist(self) -> None:
        self.assert_dirs_exist(FRONTEND_DIRS)

    def test_storage_dirs_exist(self) -> None:
        self.assert_dirs_exist(STORAGE_DIRS)

    def test_task_reports_dir_exists(self) -> None:
        self.assert_dirs_exist(["docs/task-reports"])


if __name__ == "__main__":
    unittest.main()

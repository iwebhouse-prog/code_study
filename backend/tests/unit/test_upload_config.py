"""Verifies the UPLOAD_DIR setting of AppConfig (T067)."""

import unittest
from pathlib import Path

from src.config import REPO_ROOT, AppConfig


class TestUploadDir(unittest.TestCase):
    def test_defaults_to_storage_uploads_in_the_repository(self) -> None:
        config = AppConfig.from_env({})
        self.assertEqual(config.upload_dir, REPO_ROOT / "storage" / "uploads")

    def test_relative_value_is_resolved_against_the_repository_root(self) -> None:
        config = AppConfig.from_env({"UPLOAD_DIR": "./data/files"})
        self.assertEqual(config.upload_dir, REPO_ROOT / "data" / "files")

    def test_absolute_value_is_kept(self) -> None:
        absolute = Path(REPO_ROOT.anchor) / "uploads-elsewhere"
        config = AppConfig.from_env({"UPLOAD_DIR": str(absolute)})
        self.assertEqual(config.upload_dir, absolute)

    def test_blank_value_uses_the_default(self) -> None:
        config = AppConfig.from_env({"UPLOAD_DIR": "  "})
        self.assertEqual(config.upload_dir, REPO_ROOT / "storage" / "uploads")

    def test_can_be_set_directly(self) -> None:
        directory = Path("somewhere")
        self.assertEqual(AppConfig(upload_dir=directory).upload_dir, directory)

"""Verifies the UploadedCode model definition (T062)."""

import unittest
import uuid

from sqlalchemy import CheckConstraint, Integer, String

from src.models import Task, UploadedCode
from src.models.base import Base


def column(name: str):  # type: ignore[no-untyped-def]
    return UploadedCode.__table__.c[name]


class TestUploadedCodeTable(unittest.TestCase):
    def test_table_name_and_metadata(self) -> None:
        self.assertEqual(UploadedCode.__tablename__, "uploaded_code")
        self.assertIs(Base.metadata.tables["uploaded_code"], UploadedCode.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(UploadedCode.__table__.c.keys()),
            {
                "id",
                "task_id",
                "detected_language",
                "complexity_level",
                "total_lines",
                "total_files",
                "upload_size_bytes",
                "created_at",
            },
        )

    def test_task_id_is_unique_and_cascades_from_tasks(self) -> None:
        task_id = column("task_id")
        self.assertFalse(task_id.nullable)
        self.assertTrue(task_id.unique)  # one uploaded code per task
        foreign_key = next(iter(task_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "tasks.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_optional_metadata_columns(self) -> None:
        self.assertEqual(column("detected_language").type.length, 50)
        self.assertEqual(column("complexity_level").type.length, 20)
        self.assertIsInstance(column("detected_language").type, String)
        for name in ("total_lines", "total_files", "upload_size_bytes"):
            self.assertIsInstance(column(name).type, Integer)
            self.assertTrue(column(name).nullable)

    def test_created_at_defaults_to_now(self) -> None:
        created_at = column("created_at")
        self.assertTrue(created_at.type.timezone)
        self.assertIsNotNone(created_at.server_default)

    def test_has_no_updated_at(self) -> None:
        # Migration 001 gives uploaded_code only created_at: uploads are not edited.
        self.assertNotIn("updated_at", UploadedCode.__table__.c)

    def test_checks_match_migration(self) -> None:
        checks = {
            c.name: str(c.sqltext)
            for c in UploadedCode.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        # FR-014: uploads are limited to 10MB.
        self.assertIn("upload_size_bytes <= 10485760", checks["valid_upload_size"])
        for level in ("'beginner'", "'intermediate'", "'advanced'"):
            self.assertIn(level, checks["uploaded_code_complexity_level_check"])

    def test_constants(self) -> None:
        self.assertEqual(
            UploadedCode.COMPLEXITY_LEVELS, ("beginner", "intermediate", "advanced")
        )
        self.assertEqual(UploadedCode.MAX_UPLOAD_BYTES, 10 * 1024 * 1024)


class TestRelationships(unittest.TestCase):
    def test_uploaded_code_and_task_point_at_each_other(self) -> None:
        self.assertIs(UploadedCode.task.property.mapper.class_, Task)
        self.assertIs(Task.uploaded_code.property.mapper.class_, UploadedCode)

    def test_task_has_at_most_one_uploaded_code(self) -> None:
        self.assertFalse(Task.uploaded_code.property.uselist)

    def test_relationships_never_lazy_load(self) -> None:
        self.assertEqual(UploadedCode.task.property.lazy, "raise")
        self.assertEqual(Task.uploaded_code.property.lazy, "raise")
        self.assertTrue(Task.uploaded_code.property.passive_deletes)


class TestUploadedCodeInstance(unittest.TestCase):
    def test_repr_names_language_and_size(self) -> None:
        code = UploadedCode(
            id=uuid.uuid4(), detected_language="python", upload_size_bytes=1234
        )
        self.assertIn("python", repr(code))
        self.assertIn("1234", repr(code))

"""Verifies the CodeFile model definition (T063)."""

import unittest
import uuid

from sqlalchemy import CheckConstraint, Integer, String, Text

from src.models import CodeFile, UploadedCode
from src.models.base import Base


def column(name: str):  # type: ignore[no-untyped-def]
    return CodeFile.__table__.c[name]


class TestCodeFileTable(unittest.TestCase):
    def test_table_name_and_metadata(self) -> None:
        self.assertEqual(CodeFile.__tablename__, "code_files")
        self.assertIs(Base.metadata.tables["code_files"], CodeFile.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(CodeFile.__table__.c.keys()),
            {
                "id",
                "uploaded_code_id",
                "file_name",
                "file_path",
                "file_extension",
                "file_size_bytes",
                "storage_path",
                "mime_type",
                "created_at",
            },
        )

    def test_uploaded_code_id_cascades_from_uploaded_code(self) -> None:
        uploaded_code_id = column("uploaded_code_id")
        self.assertFalse(uploaded_code_id.nullable)
        self.assertFalse(uploaded_code_id.unique)  # many files per upload
        foreign_key = next(iter(uploaded_code_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "uploaded_code.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_required_columns(self) -> None:
        self.assertEqual(column("file_name").type.length, 255)
        self.assertFalse(column("file_name").nullable)
        self.assertIsInstance(column("storage_path").type, Text)
        self.assertFalse(column("storage_path").nullable)

    def test_optional_columns(self) -> None:
        self.assertIsInstance(column("file_path").type, Text)
        self.assertEqual(column("file_extension").type.length, 20)
        self.assertIsInstance(column("mime_type").type, String)
        self.assertEqual(column("mime_type").type.length, 100)
        self.assertIsInstance(column("file_size_bytes").type, Integer)
        for name in ("file_path", "file_extension", "file_size_bytes", "mime_type"):
            self.assertTrue(column(name).nullable)

    def test_created_at_defaults_to_now_and_there_is_no_updated_at(self) -> None:
        self.assertIsNotNone(column("created_at").server_default)
        self.assertNotIn("updated_at", CodeFile.__table__.c)

    def test_extension_check_matches_the_constant(self) -> None:
        # FR-015: only these extensions may be uploaded.
        checks = {
            c.name: str(c.sqltext)
            for c in CodeFile.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        check = checks["supported_extension"]
        for extension in CodeFile.SUPPORTED_EXTENSIONS:
            self.assertIn(f"'{extension}'", check)
        self.assertEqual(check.count("'."), len(CodeFile.SUPPORTED_EXTENSIONS))

    def test_supported_extensions_constant(self) -> None:
        self.assertEqual(
            CodeFile.SUPPORTED_EXTENSIONS,
            (
                ".py",
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".html",
                ".css",
                ".java",
                ".cpp",
                ".c",
                ".txt",
                ".md",
            ),
        )


class TestRelationships(unittest.TestCase):
    def test_code_file_and_uploaded_code_point_at_each_other(self) -> None:
        self.assertIs(CodeFile.uploaded_code.property.mapper.class_, UploadedCode)
        self.assertIs(UploadedCode.files.property.mapper.class_, CodeFile)

    def test_uploaded_code_has_many_files(self) -> None:
        self.assertTrue(UploadedCode.files.property.uselist)

    def test_relationships_never_lazy_load(self) -> None:
        self.assertEqual(CodeFile.uploaded_code.property.lazy, "raise")
        self.assertEqual(UploadedCode.files.property.lazy, "raise")
        self.assertTrue(UploadedCode.files.property.passive_deletes)

    def test_files_are_listed_by_path_then_name(self) -> None:
        order_by = UploadedCode.files.property.order_by
        self.assertEqual([c.name for c in order_by], ["file_path", "file_name"])


class TestCodeFileInstance(unittest.TestCase):
    def test_repr_names_the_file(self) -> None:
        code_file = CodeFile(id=uuid.uuid4(), file_name="main.py", file_size_bytes=120)
        self.assertIn("main.py", repr(code_file))
        self.assertIn("120", repr(code_file))

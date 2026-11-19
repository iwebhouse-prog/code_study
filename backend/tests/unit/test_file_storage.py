"""Verifies the file storage service on a temporary directory (T067)."""

import tempfile
import unittest
import uuid
from pathlib import Path

from src.api.error_messages import TASK_MESSAGES
from src.api.exceptions import NotFoundError
from src.services.code_analysis.file_storage import FileMissingError, FileStorage

USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
TASK_ID = uuid.UUID("87654321-4321-8765-4321-876543218765")


class StorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.storage = FileStorage(self.root)


class TestSave(StorageTestCase):
    def test_saves_under_user_and_task_folders_with_a_uuid_name(self) -> None:
        stored = self.storage.save(USER_ID, TASK_ID, ".py", "print(1)\n")
        path = self.root / stored
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent, self.root / str(USER_ID) / str(TASK_ID))
        self.assertEqual(path.suffix, ".py")
        uuid.UUID(path.stem)  # the stem is a UUID, never the user's file name

    def test_every_save_gets_its_own_name(self) -> None:
        first = self.storage.save(USER_ID, TASK_ID, ".py", "a")
        second = self.storage.save(USER_ID, TASK_ID, ".py", "a")
        self.assertNotEqual(first, second)

    def test_stores_utf8_with_lf_line_endings(self) -> None:
        stored = self.storage.save(USER_ID, TASK_ID, ".txt", "한글\r\n둘째\r셋째\n")
        data = (self.root / stored).read_bytes()
        self.assertEqual(data, "한글\n둘째\n셋째\n".encode())

    def test_creates_missing_upload_directory(self) -> None:
        storage = FileStorage(self.root / "deep" / "uploads")
        stored = storage.save(USER_ID, TASK_ID, ".c", "int x;\n")
        self.assertTrue((self.root / "deep" / "uploads" / stored).is_file())


class TestRead(StorageTestCase):
    def test_reads_back_what_was_saved(self) -> None:
        stored = self.storage.save(USER_ID, TASK_ID, ".md", "# 제목\r\n본문")
        self.assertEqual(self.storage.read(stored), "# 제목\n본문")

    def test_missing_file_raises_file_missing(self) -> None:
        with self.assertRaises(FileMissingError) as caught:
            self.storage.read(f"{USER_ID}/{TASK_ID}/{uuid.uuid4()}.py")
        error = caught.exception
        self.assertIsInstance(error, NotFoundError)
        self.assertEqual(error.error, "file_missing")
        self.assertEqual(error.message, TASK_MESSAGES["file_missing"])
        self.assertEqual(
            error.message, "코드 파일을 찾을 수 없습니다. 다시 업로드하세요."
        )

    def test_path_outside_the_upload_directory_counts_as_missing(self) -> None:
        outside = self.root.parent / "outside-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        self.addCleanup(outside.unlink)
        with self.assertRaises(FileMissingError):
            self.storage.read("../outside-secret.txt")


class TestDelete(StorageTestCase):
    def test_deletes_the_given_files(self) -> None:
        first = self.storage.save(USER_ID, TASK_ID, ".py", "a")
        second = self.storage.save(USER_ID, TASK_ID, ".py", "b")
        self.storage.delete([first, second])
        self.assertFalse((self.root / first).exists())
        self.assertFalse((self.root / second).exists())

    def test_removes_the_task_folder_when_it_becomes_empty(self) -> None:
        stored = self.storage.save(USER_ID, TASK_ID, ".py", "a")
        self.storage.delete([stored])
        self.assertFalse((self.root / str(USER_ID) / str(TASK_ID)).exists())

    def test_keeps_other_files_in_the_task_folder(self) -> None:
        first = self.storage.save(USER_ID, TASK_ID, ".py", "a")
        second = self.storage.save(USER_ID, TASK_ID, ".py", "b")
        self.storage.delete([first])
        self.assertTrue((self.root / second).is_file())

    def test_ignores_files_that_are_already_gone(self) -> None:
        self.storage.delete([f"{USER_ID}/{TASK_ID}/{uuid.uuid4()}.py"])

    def test_never_deletes_outside_the_upload_directory(self) -> None:
        outside = self.root.parent / "outside-keep.txt"
        outside.write_text("keep", encoding="utf-8")
        self.addCleanup(outside.unlink)
        self.storage.delete(["../outside-keep.txt"])
        self.assertTrue(outside.exists())

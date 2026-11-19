"""Stores uploaded code on disk (T067, contracts/tasks-api.md "Storage").

Layout: {upload_dir}/{user_id}/{task_id}/{uuid}{ext}. The disk name is a fresh
UUID, never the user's file name, so no upload can choose where it is written.
The database keeps the path relative to the upload directory, so the directory
can move without breaking stored rows.
"""

import contextlib
import uuid
from collections.abc import Iterable
from pathlib import Path

from src.api.error_messages import TASK_MESSAGES
from src.api.exceptions import NotFoundError


class FileMissingError(NotFoundError):
    error = "file_missing"
    message = TASK_MESSAGES["file_missing"]


def _to_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self, user_id: uuid.UUID, task_id: uuid.UUID, extension: str, text: str
    ) -> str:
        """Writes the text as UTF-8 with LF line endings; returns the stored path."""
        relative = f"{user_id}/{task_id}/{uuid.uuid4()}{extension}"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # write_bytes: text mode would turn "\n" into "\r\n" on Windows.
        path.write_bytes(_to_lf(text).encode("utf-8"))
        return relative

    def read(self, stored_path: str) -> str:
        path = self._inside_root(stored_path)
        try:
            return path.read_bytes().decode("utf-8")
        except FileNotFoundError:
            raise FileMissingError() from None

    def delete(self, stored_paths: Iterable[str]) -> None:
        """Removes files (and their folder once empty); already-gone files are fine."""
        for stored_path in stored_paths:
            try:
                path = self._inside_root(stored_path)
            except FileMissingError:
                continue
            path.unlink(missing_ok=True)
            self._remove_if_empty(path.parent)

    def _inside_root(self, stored_path: str) -> Path:
        path = (self.root / stored_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise FileMissingError()
        return path

    def _remove_if_empty(self, folder: Path) -> None:
        # OSError: the folder is not empty (or already gone); nothing to do.
        with contextlib.suppress(OSError):
            folder.rmdir()

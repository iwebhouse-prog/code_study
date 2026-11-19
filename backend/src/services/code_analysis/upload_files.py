"""Turns raw uploads into checked, decoded files (T069, contracts/tasks-api.md).

Pure functions, no database or disk. Checks run in the contract's order and
stop at the first failure: excluded paths are dropped, then file count, total
size, and for each file its path, extension, binary content and encoding.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from src.api.error_messages import TASK_MESSAGES, UPLOAD_MESSAGES
from src.api.exceptions import FieldValidationError
from src.services.code_analysis.language_detector import (
    LANGUAGE_BY_EXTENSION,
    SUPPORTED_LANGUAGES,
)
from src.utils.file_validator import (
    UploadError,
    is_excluded_path,
    validate_extension,
    validate_file_count,
    validate_text,
    validate_total_size,
)

FILE_NAME_MAX_LENGTH = 255  # code_files.file_name is VARCHAR(255)
# Tried in order: UTF-8 (a BOM is dropped), then the Korean Windows code page.
ENCODINGS = ("utf-8-sig", "cp949")
_DRIVE_PREFIX = re.compile(r"[A-Za-z]:")

# "python" -> ".py": the first extension each language has.
PASTE_EXTENSIONS: dict[str, str] = {}
for _extension, _language in LANGUAGE_BY_EXTENSION.items():
    PASTE_EXTENSIONS.setdefault(_language, _extension)


class InvalidFilePathError(UploadError):
    error = "invalid_file_path"
    message = UPLOAD_MESSAGES[error]


class UnsupportedEncodingError(UploadError):
    error = "unsupported_encoding"
    message = UPLOAD_MESSAGES[error]


@dataclass(frozen=True)
class IncomingFile:
    """One uploaded part: the file name (folder uploads: the relative path)."""

    path: str
    content: bytes


@dataclass(frozen=True)
class PastedCode:
    code: str
    language: str | None


@dataclass(frozen=True)
class PreparedFile:
    """A file that passed every check; `size_bytes` is the size as uploaded."""

    file_name: str
    file_path: str
    extension: str
    size_bytes: int
    text: str


def safe_relative_path(path: str) -> str:
    """The path with "/" separators and no empty or "." parts.

    Absolute paths, ".." parts and over-long names are refused, so a name can
    never point outside the uploaded folder.
    """
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if (
        normalized.startswith("/")
        or _DRIVE_PREFIX.match(normalized)
        or "\x00" in normalized
        or ".." in parts
        or not parts
        or len(parts[-1]) > FILE_NAME_MAX_LENGTH
    ):
        raise InvalidFilePathError({"file_name": path})
    return "/".join(parts)


def decode_text(path: str, content: bytes) -> str:
    for encoding in ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedEncodingError({"file_name": path})


def _prepare_file(file: IncomingFile, upload_method: str) -> PreparedFile:
    path = safe_relative_path(file.path)
    extension = validate_extension(path)
    validate_text(path, file.content)
    text = decode_text(path, file.content)
    file_name = path.rsplit("/", 1)[-1]
    # Only folder uploads keep directories; a single file is just its name.
    file_path = path if upload_method == "folder" else file_name
    return PreparedFile(file_name, file_path, extension, len(file.content), text)


def prepare_files(
    files: Sequence[IncomingFile], upload_method: str
) -> tuple[list[PreparedFile], list[str]]:
    """Checks a file or folder upload; returns the files and the excluded paths."""
    kept = [file for file in files if not is_excluded_path(file.path)]
    excluded = [file.path for file in files if is_excluded_path(file.path)]
    validate_file_count(len(kept))
    validate_total_size(sum(len(file.content) for file in kept))
    return [_prepare_file(file, upload_method) for file in kept], excluded


def prepare_pasted_code(pasted: PastedCode) -> list[PreparedFile]:
    """Pasted code becomes one file named `pasted<ext>` (language's first ext)."""
    if not pasted.code.strip():
        raise FieldValidationError("code", TASK_MESSAGES["code_required"])
    if pasted.language not in SUPPORTED_LANGUAGES:
        raise FieldValidationError("language", TASK_MESSAGES["language_required"])
    extension = PASTE_EXTENSIONS[pasted.language]
    file_name = f"pasted{extension}"
    content = pasted.code.encode("utf-8")
    validate_total_size(len(content))
    validate_text(file_name, content)
    return [PreparedFile(file_name, file_name, extension, len(content), pasted.code)]

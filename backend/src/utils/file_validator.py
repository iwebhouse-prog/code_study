"""Checks uploaded files before anything is stored (FR-014 to FR-018).

Pure functions over file names and bytes, so the upload service (T069) can run
them on files, folders and pasted code alike. Each failure is an AppError with
a Korean message, so the API returns the shared error format (CHK084).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from src.api.error_messages import UPLOAD_MESSAGES, UPLOAD_SUGGESTIONS
from src.api.exceptions import AppError
from src.models.code_file import CodeFile
from src.models.uploaded_code import UploadedCode

MAX_FILES_PER_UPLOAD = 20  # FR-018
EXCLUDED_NAMES = frozenset({".git", "node_modules", ".DS_Store", "__pycache__"})

# Only the start of a file is inspected, so huge files are checked quickly.
BINARY_SNIFF_BYTES = 8192
BINARY_SIGNATURES = (
    b"\x89PNG",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF8",  # GIF
    b"%PDF",  # PDF
    b"PK\x03\x04",  # ZIP, and so .docx, .jar, ...
    b"\x1f\x8b",  # gzip
    b"MZ",  # Windows executable
    b"\x7fELF",  # Linux executable
    b"\xca\xfe\xba\xbe",  # Java .class
)

_MB = 1024 * 1024


class UploadError(AppError):
    def __init__(self, details: dict[str, object] | None = None) -> None:
        super().__init__(details=details, suggestion=UPLOAD_SUGGESTIONS[self.error])


class UnsupportedFileTypeError(UploadError):
    error = "unsupported_file_type"
    message = UPLOAD_MESSAGES[error]


class BinaryFileError(UploadError):
    error = "binary_file"
    message = UPLOAD_MESSAGES[error]


class FileTooLargeError(UploadError):
    status_code = 413
    error = "file_too_large"
    message = UPLOAD_MESSAGES[error]


class TooManyFilesError(UploadError):
    error = "too_many_files"
    message = UPLOAD_MESSAGES[error]


class NoFilesError(UploadError):
    error = "no_files"
    message = UPLOAD_MESSAGES[error]


@dataclass(frozen=True)
class ValidatedFile:
    """A file that passed every check, with its extension in lower case."""

    file_name: str
    extension: str
    size_bytes: int


def _posix(path: str) -> PurePosixPath:
    # Browsers on Windows may send backslashes in folder-upload paths.
    return PurePosixPath(path.replace("\\", "/"))


def file_extension(file_name: str) -> str | None:
    """The lower-case extension of a file name or path, or None if it has none."""
    suffix = _posix(file_name).suffix
    return suffix.lower() or None


def validate_extension(file_name: str) -> str:
    """Returns the normalised extension; rejects unsupported or missing ones."""
    extension = file_extension(file_name)
    if extension not in CodeFile.SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            {
                "file_name": file_name,
                "extension": extension,
                "supported_extensions": list(CodeFile.SUPPORTED_EXTENSIONS),
            }
        )
    return extension


def is_binary(content: bytes) -> bool:
    """True for a known binary signature or a NUL byte near the start.

    Text in any 8-bit encoding (UTF-8, CP949, ...) has no NUL bytes, so Korean
    code saved by older Windows editors still counts as text.
    """
    head = content[:BINARY_SNIFF_BYTES]
    return head.startswith(BINARY_SIGNATURES) or b"\x00" in head


def validate_text(file_name: str, content: bytes) -> None:
    if is_binary(content):
        raise BinaryFileError({"file_name": file_name})


def validate_total_size(total_bytes: int) -> None:
    """FR-014: an upload may be at most 10MB in total."""
    if total_bytes > UploadedCode.MAX_UPLOAD_BYTES:
        raise FileTooLargeError(
            {
                "max_size_mb": UploadedCode.MAX_UPLOAD_BYTES // _MB,
                # Rounded up: 10MB + 1 byte must not read as "10.0MB".
                "uploaded_size_mb": math.ceil(total_bytes * 10 / _MB) / 10,
            }
        )


def validate_file_count(count: int) -> None:
    """FR-018: an upload has 1 to 20 files."""
    if count < 1:
        raise NoFilesError()
    if count > MAX_FILES_PER_UPLOAD:
        raise TooManyFilesError(
            {"max_files": MAX_FILES_PER_UPLOAD, "uploaded_files": count}
        )


def is_excluded_path(path: str) -> bool:
    """FR-017: folder uploads leave out .git, node_modules, .DS_Store, __pycache__."""
    return any(part in EXCLUDED_NAMES for part in _posix(path).parts)


def validate_upload(files: Sequence[tuple[str, bytes]]) -> list[ValidatedFile]:
    """Runs every check on (name or relative path, content) pairs.

    Cheap whole-upload checks come first, then each file in order, so the
    error names the first file that fails. Excluded folders must already have
    been filtered out with is_excluded_path.
    """
    validate_file_count(len(files))
    validate_total_size(sum(len(content) for _, content in files))
    validated = []
    for file_name, content in files:
        extension = validate_extension(file_name)
        validate_text(file_name, content)
        validated.append(ValidatedFile(file_name, extension, len(content)))
    return validated

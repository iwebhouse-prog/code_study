"""Verifies the upload file checks: extension, size, count, binary content (T064)."""

import unittest

from src.api.error_messages import UPLOAD_MESSAGES
from src.models import CodeFile, UploadedCode
from src.utils.file_validator import (
    MAX_FILES_PER_UPLOAD,
    BinaryFileError,
    FileTooLargeError,
    NoFilesError,
    TooManyFilesError,
    UnsupportedFileTypeError,
    ValidatedFile,
    file_extension,
    is_binary,
    is_excluded_path,
    validate_extension,
    validate_file_count,
    validate_text,
    validate_total_size,
    validate_upload,
)

MB = 1024 * 1024


class TestFileExtension(unittest.TestCase):
    def test_lower_cases_the_extension(self) -> None:
        self.assertEqual(file_extension("MAIN.PY"), ".py")
        self.assertEqual(file_extension("App.JSX"), ".jsx")

    def test_uses_the_last_suffix_of_the_file_name(self) -> None:
        self.assertEqual(file_extension("archive.tar.gz"), ".gz")
        self.assertEqual(file_extension("src/app.min.js"), ".js")

    def test_reads_the_name_part_of_a_path(self) -> None:
        self.assertEqual(file_extension("src/v1.2/readme"), None)
        self.assertEqual(file_extension("src\\utils\\helper.ts"), ".ts")

    def test_files_without_extension_have_none(self) -> None:
        for name in ("Makefile", ".gitignore", "notes."):
            with self.subTest(name=name):
                self.assertIsNone(file_extension(name))


class TestValidateExtension(unittest.TestCase):
    def test_every_supported_extension_passes_in_any_case(self) -> None:
        for extension in CodeFile.SUPPORTED_EXTENSIONS:
            with self.subTest(extension=extension):
                self.assertEqual(validate_extension(f"a{extension}"), extension)
                self.assertEqual(validate_extension(f"A{extension.upper()}"), extension)

    def test_unsupported_extension_is_rejected_in_korean(self) -> None:
        with self.assertRaises(UnsupportedFileTypeError) as caught:
            validate_extension("setup.exe")
        error = caught.exception
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error, "unsupported_file_type")
        self.assertEqual(error.message, UPLOAD_MESSAGES["unsupported_file_type"])
        assert error.details is not None
        self.assertEqual(error.details["file_name"], "setup.exe")
        self.assertEqual(error.details["extension"], ".exe")
        self.assertEqual(
            error.details["supported_extensions"], list(CodeFile.SUPPORTED_EXTENSIONS)
        )
        self.assertIsNotNone(error.suggestion)

    def test_missing_extension_is_rejected(self) -> None:
        # The database check lets a NULL extension through (T063), so stop it here.
        with self.assertRaises(UnsupportedFileTypeError) as caught:
            validate_extension("Makefile")
        assert caught.exception.details is not None
        self.assertIsNone(caught.exception.details["extension"])


class TestBinaryDetection(unittest.TestCase):
    def test_source_code_is_text(self) -> None:
        self.assertFalse(is_binary(b"def add(a, b):\n    return a + b\n"))

    def test_korean_utf8_and_cp949_are_text(self) -> None:
        self.assertFalse(is_binary("# 합계 계산\nprint('안녕')\n".encode()))
        self.assertFalse(is_binary("# 합계 계산\n".encode("cp949")))

    def test_utf8_bom_and_crlf_are_text(self) -> None:
        self.assertFalse(is_binary(b"\xef\xbb\xbfconsole.log(1);\r\n"))

    def test_empty_content_is_text(self) -> None:
        self.assertFalse(is_binary(b""))

    def test_nul_byte_means_binary(self) -> None:
        self.assertTrue(is_binary(b"print(1)\x00\x01\x02"))

    def test_known_binary_signatures_are_binary(self) -> None:
        signatures = {
            "png": b"\x89PNG\r\n\x1a\n",
            "jpeg": b"\xff\xd8\xff\xe0",
            "gif": b"GIF89a",
            "pdf": b"%PDF-1.7",
            "zip": b"PK\x03\x04",
            "gzip": b"\x1f\x8b\x08",
            "windows exe": b"MZ\x90",
            "elf": b"\x7fELF",
            "java class": b"\xca\xfe\xba\xbe",
        }
        for kind, signature in signatures.items():
            with self.subTest(kind=kind):
                # Text-looking bytes after the signature must not hide it.
                self.assertTrue(is_binary(signature + b"looks like text"))

    def test_nul_byte_after_the_first_8kb_is_not_inspected(self) -> None:
        self.assertFalse(is_binary(b"a" * 8192 + b"\x00"))

    def test_validate_text_rejects_binary_in_korean(self) -> None:
        with self.assertRaises(BinaryFileError) as caught:
            validate_text("logo.py", b"\x89PNG\r\n\x1a\n")
        error = caught.exception
        self.assertEqual((error.status_code, error.error), (400, "binary_file"))
        self.assertEqual(error.message, UPLOAD_MESSAGES["binary_file"])
        self.assertEqual(error.details, {"file_name": "logo.py"})
        self.assertIsNotNone(error.suggestion)

    def test_validate_text_accepts_text(self) -> None:
        validate_text("main.py", b"print('hi')\n")


class TestTotalSize(unittest.TestCase):
    def test_exactly_ten_megabytes_passes(self) -> None:
        self.assertEqual(UploadedCode.MAX_UPLOAD_BYTES, 10 * MB)
        validate_total_size(10 * MB)

    def test_over_ten_megabytes_is_rejected_with_the_chk084_body(self) -> None:
        with self.assertRaises(FileTooLargeError) as caught:
            validate_total_size(int(15.3 * MB))
        error = caught.exception
        self.assertEqual((error.status_code, error.error), (413, "file_too_large"))
        self.assertEqual(error.message, "파일 크기가 10MB를 초과합니다.")
        self.assertEqual(error.details, {"max_size_mb": 10, "uploaded_size_mb": 15.3})
        self.assertEqual(
            error.suggestion,
            "더 작은 파일을 선택하거나 코드를 여러 태스크로 나누어 업로드하세요.",
        )

    def test_one_byte_over_still_reports_more_than_ten(self) -> None:
        with self.assertRaises(FileTooLargeError) as caught:
            validate_total_size(10 * MB + 1)
        assert caught.exception.details is not None
        self.assertGreater(caught.exception.details["uploaded_size_mb"], 10)


class TestFileCount(unittest.TestCase):
    def test_one_to_twenty_files_pass(self) -> None:
        self.assertEqual(MAX_FILES_PER_UPLOAD, 20)
        for count in (1, 20):
            validate_file_count(count)

    def test_no_files_is_rejected(self) -> None:
        with self.assertRaises(NoFilesError) as caught:
            validate_file_count(0)
        self.assertEqual(caught.exception.error, "no_files")
        self.assertEqual(caught.exception.message, UPLOAD_MESSAGES["no_files"])

    def test_more_than_twenty_files_is_rejected(self) -> None:
        with self.assertRaises(TooManyFilesError) as caught:
            validate_file_count(100)
        error = caught.exception
        self.assertEqual((error.status_code, error.error), (400, "too_many_files"))
        self.assertEqual(error.message, UPLOAD_MESSAGES["too_many_files"])
        self.assertEqual(error.details, {"max_files": 20, "uploaded_files": 100})


class TestExcludedPaths(unittest.TestCase):
    def test_system_and_build_folders_are_excluded(self) -> None:
        # FR-017: .git, node_modules, .DS_Store, __pycache__ are left out.
        for path in (
            ".git/config",
            "node_modules/react/index.js",
            "src/__pycache__/app.cpython-312.pyc",
            ".DS_Store",
            "src/.DS_Store",
            "web\\node_modules\\x.js",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_excluded_path(path))

    def test_ordinary_paths_are_kept(self) -> None:
        for path in ("src/app.js", "my_node_modules.md", "docs/git-guide.md"):
            with self.subTest(path=path):
                self.assertFalse(is_excluded_path(path))


class TestValidateUpload(unittest.TestCase):
    def test_returns_normalised_details_for_each_file(self) -> None:
        result = validate_upload(
            [("src/App.JSX", b"export default App\n"), ("README.md", b"# Todo\n")]
        )
        self.assertEqual(
            result,
            [
                ValidatedFile("src/App.JSX", ".jsx", 19),
                ValidatedFile("README.md", ".md", 7),
            ],
        )

    def test_count_is_checked_before_anything_else(self) -> None:
        files = [(f"f{i}.exe", b"\x00") for i in range(21)]
        with self.assertRaises(TooManyFilesError):
            validate_upload(files)

    def test_total_size_is_checked_across_all_files(self) -> None:
        files = [("a.txt", b"a" * (6 * MB)), ("b.txt", b"b" * (5 * MB))]
        with self.assertRaises(FileTooLargeError):
            validate_upload(files)

    def test_first_bad_file_is_named(self) -> None:
        with self.assertRaises(UnsupportedFileTypeError) as caught:
            validate_upload([("ok.py", b"x"), ("photo.png", b"x")])
        assert caught.exception.details is not None
        self.assertEqual(caught.exception.details["file_name"], "photo.png")

    def test_binary_content_with_a_code_extension_is_rejected(self) -> None:
        with self.assertRaises(BinaryFileError):
            validate_upload([("disguised.js", b"\x7fELF\x02\x01")])

    def test_empty_upload_is_rejected(self) -> None:
        with self.assertRaises(NoFilesError):
            validate_upload([])

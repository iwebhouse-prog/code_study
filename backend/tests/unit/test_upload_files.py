"""Verifies how uploads are prepared before anything is stored (T069)."""

import unittest

from src.api.error_messages import TASK_MESSAGES, UPLOAD_MESSAGES, UPLOAD_SUGGESTIONS
from src.api.exceptions import AppError, FieldValidationError
from src.models.uploaded_code import UploadedCode
from src.services.code_analysis.language_detector import SUPPORTED_LANGUAGES
from src.services.code_analysis.upload_files import (
    IncomingFile,
    InvalidFilePathError,
    PastedCode,
    UnsupportedEncodingError,
    prepare_files,
    prepare_pasted_code,
)


def incoming(path: str, content: bytes = b"print(1)\n") -> IncomingFile:
    return IncomingFile(path, content)


def error_of(call: object) -> AppError:
    assert callable(call)
    with unittest.TestCase().assertRaises(AppError) as caught:
        call()
    return caught.exception


class TestMessages(unittest.TestCase):
    def test_texts_follow_the_contract(self) -> None:
        self.assertEqual(
            UPLOAD_MESSAGES["unsupported_encoding"],
            "파일의 문자 인코딩을 읽을 수 없습니다.",
        )
        self.assertEqual(
            UPLOAD_MESSAGES["invalid_file_path"], "파일 경로가 올바르지 않습니다."
        )
        self.assertIn("UTF-8", UPLOAD_SUGGESTIONS["unsupported_encoding"])
        self.assertEqual(TASK_MESSAGES["code_required"], "붙여넣을 코드를 입력하세요.")
        self.assertEqual(
            TASK_MESSAGES["language_required"], "프로그래밍 언어를 선택하세요."
        )

    def test_errors_are_400s_with_details_and_a_suggestion(self) -> None:
        for error_class, code in (
            (InvalidFilePathError, "invalid_file_path"),
            (UnsupportedEncodingError, "unsupported_encoding"),
        ):
            with self.subTest(code=code):
                error = error_class({"file_name": "a.py"})
                self.assertEqual((error.status_code, error.error), (400, code))
                self.assertEqual(error.message, UPLOAD_MESSAGES[code])
                self.assertEqual(error.suggestion, UPLOAD_SUGGESTIONS[code])
                self.assertEqual(error.details, {"file_name": "a.py"})


class TestPrepareFiles(unittest.TestCase):
    def test_prepares_a_single_file(self) -> None:
        prepared, excluded = prepare_files([incoming("App.PY", b"x = 1\r\n")], "file")
        (file,) = prepared
        self.assertEqual(
            (file.file_name, file.file_path, file.extension, file.size_bytes),
            ("App.PY", "App.PY", ".py", 7),
        )
        self.assertEqual(file.text, "x = 1\r\n")
        self.assertEqual(excluded, [])

    def test_file_upload_uses_only_the_file_name(self) -> None:
        (file,), _ = prepare_files([incoming("some/dir/a.py")], "file")
        self.assertEqual((file.file_name, file.file_path), ("a.py", "a.py"))

    def test_folder_upload_keeps_the_relative_path(self) -> None:
        (file,), _ = prepare_files([incoming("my-app/src/App.jsx")], "folder")
        self.assertEqual(file.file_name, "App.jsx")
        self.assertEqual(file.file_path, "my-app/src/App.jsx")

    def test_path_is_normalised(self) -> None:
        (file,), _ = prepare_files([incoming("my-app\\src\\.\\//a.py")], "folder")
        self.assertEqual(file.file_path, "my-app/src/a.py")

    def test_excluded_paths_are_dropped_and_listed_in_order(self) -> None:
        files = [
            incoming("app/node_modules/react/index.js"),
            incoming("app/main.py"),
            incoming(".git/config"),
            incoming("app/.DS_Store"),
            incoming("app/__pycache__/main.cpython-312.pyc"),
        ]
        prepared, excluded = prepare_files(files, "folder")
        self.assertEqual([f.file_path for f in prepared], ["app/main.py"])
        self.assertEqual(
            excluded,
            [
                "app/node_modules/react/index.js",
                ".git/config",
                "app/.DS_Store",
                "app/__pycache__/main.cpython-312.pyc",
            ],
        )

    def test_nothing_left_after_excluding_is_no_files(self) -> None:
        error = error_of(lambda: prepare_files([incoming(".git/config")], "folder"))
        self.assertEqual(error.error, "no_files")

    def test_no_files_at_all_is_no_files(self) -> None:
        self.assertEqual(error_of(lambda: prepare_files([], "file")).error, "no_files")

    def test_more_than_twenty_files_is_too_many_files(self) -> None:
        files = [incoming(f"f{i}.py") for i in range(21)]
        error = error_of(lambda: prepare_files(files, "folder"))
        self.assertEqual(error.error, "too_many_files")
        self.assertEqual(error.details, {"max_files": 20, "uploaded_files": 21})

    def test_excluded_files_do_not_count_toward_the_limit(self) -> None:
        files = [incoming(f"f{i}.py") for i in range(20)]
        files += [incoming(f"node_modules/m{i}.js") for i in range(30)]
        prepared, excluded = prepare_files(files, "folder")
        self.assertEqual((len(prepared), len(excluded)), (20, 30))

    def test_total_size_over_10mb_is_file_too_large(self) -> None:
        big = b"a" * (UploadedCode.MAX_UPLOAD_BYTES // 2 + 1)
        error = error_of(
            lambda: prepare_files(
                [incoming("a.py", big), incoming("b.py", big)], "file"
            )
        )
        self.assertEqual((error.status_code, error.error), (413, "file_too_large"))

    def test_count_is_checked_before_size_and_size_before_files(self) -> None:
        many = [incoming(f"../f{i}.exe") for i in range(21)]
        self.assertEqual(
            error_of(lambda: prepare_files(many, "folder")).error, "too_many_files"
        )
        big = [incoming("../f.exe", b"a" * (UploadedCode.MAX_UPLOAD_BYTES + 1))]
        self.assertEqual(
            error_of(lambda: prepare_files(big, "folder")).error, "file_too_large"
        )

    def test_unsafe_paths_are_invalid_file_paths(self) -> None:
        for path in (
            "/etc/passwd.py",
            "\\windows\\a.py",
            "C:/dir/a.py",
            "c:\\dir\\a.py",
            "../a.py",
            "app/../../a.py",
            "app\\..\\a.py",
            "a\x00b.py",
            "///",
            "",
            ".",
            "app/" + "x" * 256 + ".py",
        ):
            with self.subTest(path=repr(path)):
                error = error_of(lambda p=path: prepare_files([incoming(p)], "folder"))
                self.assertEqual(error.error, "invalid_file_path")
                self.assertEqual(error.details, {"file_name": path})

    def test_a_name_that_only_contains_dots_in_it_is_fine(self) -> None:
        (file,), _ = prepare_files([incoming("my..app/a..b.py")], "folder")
        self.assertEqual(file.file_path, "my..app/a..b.py")

    def test_path_is_checked_before_extension_and_content(self) -> None:
        error = error_of(
            lambda: prepare_files([incoming("../a.exe", b"\x00\x01")], "folder")
        )
        self.assertEqual(error.error, "invalid_file_path")

    def test_unsupported_extension_is_rejected(self) -> None:
        error = error_of(lambda: prepare_files([incoming("a.exe")], "file"))
        self.assertEqual(error.error, "unsupported_file_type")

    def test_binary_content_is_rejected_before_decoding(self) -> None:
        error = error_of(lambda: prepare_files([incoming("a.py", b"\x00\xff")], "file"))
        self.assertEqual(error.error, "binary_file")

    def test_the_first_failing_file_is_reported(self) -> None:
        files = [incoming("a.py"), incoming("b.exe"), incoming("../c.py")]
        error = error_of(lambda: prepare_files(files, "folder"))
        self.assertEqual(error.error, "unsupported_file_type")
        assert error.details is not None
        self.assertEqual(error.details["file_name"], "b.exe")


class TestDecoding(unittest.TestCase):
    def decode(self, content: bytes) -> str:
        (file,), _ = prepare_files([incoming("a.txt", content)], "file")
        return file.text

    def test_reads_utf8(self) -> None:
        self.assertEqual(self.decode("한글 코드".encode()), "한글 코드")

    def test_reads_utf8_with_a_bom_and_drops_the_bom(self) -> None:
        self.assertEqual(self.decode(b"\xef\xbb\xbfhello"), "hello")

    def test_reads_cp949(self) -> None:
        self.assertEqual(self.decode("한글 코드".encode("cp949")), "한글 코드")

    def test_ascii_is_fine(self) -> None:
        self.assertEqual(self.decode(b"plain"), "plain")

    def test_empty_file_is_fine(self) -> None:
        self.assertEqual(self.decode(b""), "")

    def test_unreadable_bytes_are_unsupported_encoding(self) -> None:
        # 0xFF is neither valid UTF-8 nor a valid CP949 lead byte.
        error = error_of(lambda: self.decode(b"abc \xff\xfe def"))
        self.assertEqual(
            (error.status_code, error.error), (400, "unsupported_encoding")
        )
        self.assertEqual(error.details, {"file_name": "a.txt"})


class TestPreparePastedCode(unittest.TestCase):
    def test_is_stored_as_pasted_with_the_languages_extension(self) -> None:
        expected = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "html": ".html",
            "css": ".css",
            "java": ".java",
            "c": ".c",
            "cpp": ".cpp",
            "markdown": ".md",
            "text": ".txt",
        }
        self.assertEqual(set(expected), set(SUPPORTED_LANGUAGES))
        for language, extension in expected.items():
            with self.subTest(language=language):
                (file,) = prepare_pasted_code(PastedCode("x = 1\n", language))
                self.assertEqual(
                    (file.file_name, file.file_path, file.extension),
                    (f"pasted{extension}", f"pasted{extension}", extension),
                )

    def test_size_is_the_utf8_length(self) -> None:
        (file,) = prepare_pasted_code(PastedCode("한글", "text"))
        self.assertEqual((file.size_bytes, file.text), (6, "한글"))

    def test_blank_code_is_a_code_field_error(self) -> None:
        for code in ("", "  \n\t "):
            with (
                self.subTest(code=repr(code)),
                self.assertRaises(FieldValidationError) as caught,
            ):
                prepare_pasted_code(PastedCode(code, "python"))
            self.assertEqual(
                caught.exception.details,
                {
                    "fields": [
                        {"field": "code", "message": "붙여넣을 코드를 입력하세요."}
                    ]
                },
            )

    def test_missing_or_unknown_language_is_a_language_field_error(self) -> None:
        for language in (None, "", "ruby", "Python"):
            with (
                self.subTest(language=language),
                self.assertRaises(FieldValidationError) as caught,
            ):
                prepare_pasted_code(PastedCode("x = 1", language))
            self.assertEqual(
                caught.exception.details,
                {
                    "fields": [
                        {
                            "field": "language",
                            "message": "프로그래밍 언어를 선택하세요.",
                        }
                    ]
                },
            )

    def test_code_is_checked_before_language(self) -> None:
        with self.assertRaises(FieldValidationError) as caught:
            prepare_pasted_code(PastedCode("", None))
        assert caught.exception.details is not None
        self.assertEqual(caught.exception.details["fields"][0]["field"], "code")

    def test_over_10mb_is_file_too_large(self) -> None:
        code = "a" * (UploadedCode.MAX_UPLOAD_BYTES + 1)
        error = error_of(lambda: prepare_pasted_code(PastedCode(code, "text")))
        self.assertEqual(error.error, "file_too_large")

    def test_code_with_a_nul_character_is_binary(self) -> None:
        error = error_of(lambda: prepare_pasted_code(PastedCode("a\x00b", "text")))
        self.assertEqual(error.error, "binary_file")

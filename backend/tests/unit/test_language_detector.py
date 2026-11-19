"""Verifies programming-language detection for uploaded code (T065, FR-020)."""

import unittest

from src.models import CodeFile, UploadedCode
from src.services.code_analysis.language_detector import (
    LANGUAGE_BY_EXTENSION,
    SUPPORTED_LANGUAGES,
    detect_file_language,
    detect_language,
)


class TestExtensionMapping(unittest.TestCase):
    def test_every_uploadable_extension_has_a_language(self) -> None:
        self.assertEqual(set(LANGUAGE_BY_EXTENSION), set(CodeFile.SUPPORTED_EXTENSIONS))

    def test_languages_are_named_as_stored(self) -> None:
        self.assertEqual(
            SUPPORTED_LANGUAGES,
            (
                "python",
                "javascript",
                "typescript",
                "html",
                "css",
                "java",
                "c",
                "cpp",
                "markdown",
                "text",
            ),
        )
        column = UploadedCode.__table__.c["detected_language"]
        self.assertTrue(
            all(len(name) <= column.type.length for name in SUPPORTED_LANGUAGES)
        )

    def test_extension_decides_the_language(self) -> None:
        cases = {
            "main.py": "python",
            "app.js": "javascript",
            "App.jsx": "javascript",
            "api.ts": "typescript",
            "Page.tsx": "typescript",
            "index.html": "html",
            "style.css": "css",
            "Main.java": "java",
            "hello.c": "c",
            "vector.cpp": "cpp",
            "README.md": "markdown",
            "src/utils/helper.PY": "python",
        }
        for file_name, language in cases.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(detect_file_language(file_name, ""), language)

    def test_extension_wins_over_contents(self) -> None:
        # A .py file holding HTML is still the user's Python file.
        self.assertEqual(
            detect_file_language("page.py", "<!DOCTYPE html><html></html>"), "python"
        )


class TestTextFileContents(unittest.TestCase):
    def test_python_shebang(self) -> None:
        for line in (
            "#!/usr/bin/env python3",
            "#!/usr/bin/python",
            "#! /usr/bin/env python",
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    detect_file_language("run.txt", f"{line}\nprint(1)\n"), "python"
                )

    def test_node_shebang(self) -> None:
        # Pygments misses this one, so the detector checks shebangs itself.
        self.assertEqual(
            detect_file_language("run.txt", "#!/usr/bin/env node\nconsole.log(1)\n"),
            "javascript",
        )

    def test_shebang_parser_reads_paths_versions_and_flags(self) -> None:
        # Text after the shebang hides the language from Pygments, so these
        # pass only through the detector's own shebang parser.
        body = "\n오늘의 메모\n"
        cases = {
            "#!/usr/bin/python3.12": "python",
            "#!/usr/bin/env -S python3 -u": "python",
            "#!/usr/local/bin/node": "javascript",
        }
        for line, language in cases.items():
            with self.subTest(line=line):
                self.assertEqual(detect_file_language("run.txt", line + body), language)

    def test_shebang_without_a_program_is_ignored(self) -> None:
        for line in ("#!", "#!/usr/bin/env", "#!/usr/bin/env -S"):
            with self.subTest(line=line):
                self.assertEqual(
                    detect_file_language("run.txt", f"{line}\n오늘의 메모\n"), "text"
                )

    def test_unknown_shebang_falls_back_to_text(self) -> None:
        self.assertEqual(
            detect_file_language("run.txt", "#!/bin/bash\necho hi\n"), "text"
        )

    def test_pygments_recognises_html_and_c(self) -> None:
        self.assertEqual(
            detect_file_language("page.txt", "<!DOCTYPE html>\n<html></html>\n"), "html"
        )
        self.assertEqual(
            detect_file_language(
                "main.txt", "#include <stdio.h>\nint main(void){return 0;}\n"
            ),
            "c",
        )

    def test_guesses_outside_the_supported_languages_become_text(self) -> None:
        # Pygments guesses "Tera Term macro" for this Python snippet.
        self.assertEqual(
            detect_file_language("notes.txt", "def add(a, b):\n    return a + b\n"),
            "text",
        )

    def test_korean_notes_and_empty_files_are_text(self) -> None:
        self.assertEqual(
            detect_file_language("notes.txt", "오늘 배운 내용\n함수는 재사용됩니다.\n"),
            "text",
        )
        self.assertEqual(detect_file_language("empty.txt", ""), "text")

    def test_only_the_start_of_a_huge_file_is_read(self) -> None:
        content = "<!DOCTYPE html>\n" + "x" * 5_000_000
        self.assertEqual(detect_file_language("big.txt", content), "html")


class TestUploadLanguage(unittest.TestCase):
    def test_single_file(self) -> None:
        self.assertEqual(detect_language([("main.py", "print(1)\n")]), "python")

    def test_language_with_the_most_lines_wins(self) -> None:
        files = [
            ("public/index.html", "<html>\n</html>\n"),
            ("src/App.jsx", "a\nb\nc\n"),
            ("src/utils.js", "d\ne\n"),
        ]
        # javascript 5 lines vs html 2 lines.
        self.assertEqual(detect_language(files), "javascript")

    def test_docs_do_not_outweigh_code(self) -> None:
        files = [("README.md", "line\n" * 100), ("main.py", "print(1)\n")]
        self.assertEqual(detect_language(files), "python")

    def test_docs_only_upload_uses_the_docs_language(self) -> None:
        files = [("README.md", "a\nb\n"), ("notes.txt", "c\n")]
        self.assertEqual(detect_language(files), "markdown")

    def test_tie_goes_to_the_file_listed_first(self) -> None:
        files = [("style.css", "a\n"), ("main.py", "b\n")]
        self.assertEqual(detect_language(files), "css")

    def test_last_line_without_newline_still_counts(self) -> None:
        files = [("a.py", "x"), ("b.css", "")]
        self.assertEqual(detect_language(files), "python")

    def test_no_files_means_no_language(self) -> None:
        self.assertIsNone(detect_language([]))

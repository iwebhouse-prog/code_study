"""Detects the programming language of uploaded code (FR-020, research.md §6).

Order of evidence for one file: its extension, then a shebang line, then a
Pygments guess from the contents. Only `.txt` files reach the last two steps,
since every other uploadable extension names its language. Pygments guesses
are kept only when they name a supported language: on short snippets it often
guesses wrongly (e.g. Python without a shebang reads as "Tera Term macro").
"""

import re
from collections.abc import Sequence

from pygments.lexers import guess_lexer

from src.utils.file_validator import file_extension

# Every extension CodeFile accepts, mapped to the name stored in
# uploaded_code.detected_language.
LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".md": "markdown",
    ".txt": "text",
}
SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(
    dict.fromkeys(LANGUAGE_BY_EXTENSION.values())
)

# Notes and plain text say little about what the code is written in.
DOCUMENT_LANGUAGES = frozenset({"markdown", "text"})

# Pygments lexer aliases that mean one of our languages.
_LANGUAGE_BY_PYGMENTS_ALIAS: dict[str, str] = {
    "python": "python",
    "python3": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "html": "html",
    "css": "css",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "markdown": "markdown",
}

# "python3.12" -> "python"
_VERSION_SUFFIX = re.compile(r"[\d.]+$")
_LANGUAGE_BY_INTERPRETER = {"python": "python", "node": "javascript"}

# Guessing reads every Pygments lexer, so look only at the start of a file.
_GUESS_CHARS = 10_000


def _from_shebang(content: str) -> str | None:
    """Reads "#!/usr/bin/python3" or "#!/usr/bin/env node" style first lines."""
    first_line = content.split("\n", 1)[0]
    if not first_line.startswith("#!"):
        return None
    words = first_line[2:].split()
    # "/usr/bin/env node": the program is the first word env is given.
    if words and words[0].rsplit("/", 1)[-1] == "env":
        words = [word for word in words[1:] if not word.startswith("-")]
    if not words:
        return None
    program = _VERSION_SUFFIX.sub("", words[0].rsplit("/", 1)[-1])
    return _LANGUAGE_BY_INTERPRETER.get(program)


def _from_pygments(content: str) -> str:
    lexer = guess_lexer(content[:_GUESS_CHARS])
    for alias in lexer.aliases:
        if alias in _LANGUAGE_BY_PYGMENTS_ALIAS:
            return _LANGUAGE_BY_PYGMENTS_ALIAS[alias]
    return "text"


def detect_file_language(file_name: str, content: str) -> str:
    """The language of one file that already passed validate_extension (T064)."""
    language = LANGUAGE_BY_EXTENSION[file_extension(file_name) or ".txt"]
    if language != "text":
        return language
    return _from_shebang(content) or _from_pygments(content)


def count_lines(content: str) -> int:
    return content.count("\n") + (1 if content and not content.endswith("\n") else 0)


def detect_language(files: Sequence[tuple[str, str]]) -> str | None:
    """The main language of an upload: the one with the most lines of code.

    Markdown and text count only when the upload has nothing else. Ties go to
    the language whose file comes first. None when there are no files.
    """
    lines: dict[str, int] = {}
    for file_name, content in files:
        language = detect_file_language(file_name, content)
        lines[language] = lines.get(language, 0) + count_lines(content)
    code = {lang: n for lang, n in lines.items() if lang not in DOCUMENT_LANGUAGES}
    candidates = code or lines
    if not candidates:
        return None
    # max() keeps the first of equal values, and dicts keep insertion order.
    return max(candidates, key=lambda language: candidates[language])

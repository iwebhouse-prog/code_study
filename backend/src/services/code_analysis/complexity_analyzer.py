"""Assesses how hard uploaded code is to read (FR-021, research.md §6).

Three measures from research.md: lines of code, nesting depth and number of
functions. They come from Pygments tokens, so comments and strings never count
as code or braces. Any one measure reaching a threshold sets the level.

The specs give no numbers; these were chosen for complete beginners. 500 lines
matches the spec's "large code" warning (Edge Cases).
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Keyword, Name, Punctuation, String, _TokenType

from src.services.code_analysis.language_detector import (
    DOCUMENT_LANGUAGES,
    count_lines,
    detect_file_language,
)
from src.utils.file_validator import file_extension


@dataclass(frozen=True)
class Limits:
    code_lines: int
    functions: int
    depth: int


INTERMEDIATE = Limits(code_lines=100, functions=5, depth=3)
ADVANCED = Limits(code_lines=500, functions=20, depth=5)

# Python nests by indentation; the others below use braces.
_INDENT_LANGUAGES = frozenset({"python"})
_BRACE_LANGUAGES = frozenset({"javascript", "typescript", "java", "c", "cpp", "css"})
# JSX and TSX lex badly as plain JavaScript/TypeScript.
_LEXER_BY_EXTENSION = {".jsx": "jsx", ".tsx": "tsx"}
_TAB_WIDTH = 4


@dataclass(frozen=True)
class FileMetrics:
    total_lines: int
    code_lines: int
    function_count: int
    max_nesting_depth: int


@dataclass(frozen=True)
class ComplexityReport:
    level: str
    total_lines: int
    code_lines: int
    function_count: int
    max_nesting_depth: int


def complexity_level(code_lines: int, functions: int, depth: int) -> str:
    """One of UploadedCode.COMPLEXITY_LEVELS."""
    for level, limits in (("advanced", ADVANCED), ("intermediate", INTERMEDIATE)):
        if (
            code_lines >= limits.code_lines
            or functions >= limits.functions
            or depth >= limits.depth
        ):
            return level
    return "beginner"


def _is_code(token_type: _TokenType, value: str) -> bool:
    if not value.strip():
        return False
    # Docstrings explain code; preprocessor lines (#include) are code.
    if token_type in String.Doc:
        return False
    return token_type not in Comment or token_type in Comment.Preproc


def _is_function(token_type: _TokenType, value: str) -> bool:
    # Python, Java and C mark definitions as Name.Function; JavaScript and
    # TypeScript do not, so their "function" keyword and arrows count instead.
    if token_type in Name.Function:
        return True
    return (token_type in Keyword and value == "function") or (
        token_type in Punctuation and value == "=>"
    )


def _tokens(
    file_name: str, language: str, content: str
) -> Iterator[tuple[_TokenType, str]]:
    alias = _LEXER_BY_EXTENSION.get(file_extension(file_name) or "", language)
    # stripnl=False keeps line numbers aligned with the original content.
    yield from get_lexer_by_name(alias, stripnl=False).get_tokens(content)


def _brace_depth(punctuation: Sequence[str]) -> int:
    depth = deepest = 0
    for value in punctuation:
        for char in value:
            if char == "{":
                depth += 1
                deepest = max(deepest, depth)
            elif char == "}":
                depth = max(depth - 1, 0)
    return deepest


def _indent_depth(content: str, code_line_numbers: set[int]) -> int:
    lines = content.split("\n")
    indents = {
        len(line) - len(line.lstrip())
        for line in (lines[n].expandtabs(_TAB_WIDTH) for n in code_line_numbers)
    }
    return max(len(indents) - 1, 0)


def analyze_file(file_name: str, content: str) -> FileMetrics:
    language = detect_file_language(file_name, content)
    code_line_numbers: set[int] = set()
    punctuation: list[str] = []
    functions = line = 0
    for token_type, value in _tokens(file_name, language, content):
        if _is_code(token_type, value):
            code_line_numbers.add(line)
        functions += _is_function(token_type, value)
        if token_type in Punctuation:
            punctuation.append(value)
        line += value.count("\n")
    if language in _INDENT_LANGUAGES:
        depth = _indent_depth(content, code_line_numbers)
    elif language in _BRACE_LANGUAGES:
        depth = _brace_depth(punctuation)
    else:
        depth = 0
    return FileMetrics(count_lines(content), len(code_line_numbers), functions, depth)


def assess_complexity(files: Sequence[tuple[str, str]]) -> ComplexityReport:
    """The level of a whole upload. Markdown and text add to total_lines only."""
    total = code = functions = depth = 0
    for file_name, content in files:
        metrics = analyze_file(file_name, content)
        total += metrics.total_lines
        if detect_file_language(file_name, content) in DOCUMENT_LANGUAGES:
            continue
        code += metrics.code_lines
        functions += metrics.function_count
        depth = max(depth, metrics.max_nesting_depth)
    return ComplexityReport(
        complexity_level(code, functions, depth), total, code, functions, depth
    )

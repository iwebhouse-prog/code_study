"""Checks a generated learning document before it is stored (FR-095, T093).

Two kinds of checks, both returning readable problem lines (the same lines go
back to the model in a retry prompt, FR-096):
- shape: a small walker over DOCUMENT_SCHEMA (types, required and unknown keys,
  blank text, list sizes, fixed titles, leftover placeholders);
- code references: chapter 3 and 4 must name uploaded files, and chapter 4's
  line numbers must exist in them.
"""

import re
from collections.abc import Iterator, Sequence
from typing import Any, TypeGuard

from src.services.ai.document_schema import DOCUMENT_SCHEMA
from src.services.ai.prompts import PromptFile
from src.services.code_analysis.language_detector import count_lines

# Fields the model may leave empty ("nothing to note").
MAY_BE_EMPTY = frozenset({"notes"})
PLACEHOLDER = re.compile(r"\[(TODO|TBD|GENERATE|PLACEHOLDER)\]", re.IGNORECASE)
ROOT = "document"


def validate_document(content: Any, files: Sequence[PromptFile]) -> list[str]:
    """Problems found in `content`; an empty list means it may be stored."""
    problems: list[str] = []
    _check(content, DOCUMENT_SCHEMA, ROOT, problems)
    if isinstance(content, dict):
        problems += _check_references(content, files)
    return problems


def _check(value: Any, schema: dict[str, Any], path: str, problems: list[str]) -> None:
    kind = schema["type"]
    if kind == "object":
        _check_object(value, schema, path, problems)
    elif kind == "array":
        _check_array(value, schema, path, problems)
    elif kind == "integer":
        # bool is a subclass of int in Python, but true/false is not a number.
        if not isinstance(value, int) or isinstance(value, bool):
            problems.append(f"{path}: 정수여야 합니다")
    else:
        _check_text(value, schema, path, problems)


def _check_object(
    value: Any, schema: dict[str, Any], path: str, problems: list[str]
) -> None:
    if not isinstance(value, dict):
        problems.append(f"{path}: 객체여야 합니다")
        return
    properties = schema["properties"]
    problems += [
        f"{path}.{key}: 빠졌습니다" for key in schema["required"] if key not in value
    ]
    for key, item in value.items():
        if key in properties:
            _check(item, properties[key], f"{path}.{key}", problems)
        else:
            problems.append(f"{path}.{key}: 정해지지 않은 항목입니다")


def _check_array(
    value: Any, schema: dict[str, Any], path: str, problems: list[str]
) -> None:
    if not isinstance(value, list):
        problems.append(f"{path}: 목록이어야 합니다")
        return
    if len(value) < schema.get("minItems", 0):
        problems.append(f"{path}: 최소 {schema['minItems']}개입니다 ({len(value)}개)")
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        problems.append(f"{path}: 최대 {schema['maxItems']}개입니다 ({len(value)}개)")
    for index, item in enumerate(value):
        _check(item, schema["items"], f"{path}[{index}]", problems)


def _check_text(
    value: Any, schema: dict[str, Any], path: str, problems: list[str]
) -> None:
    if not isinstance(value, str):
        problems.append(f"{path}: 글이어야 합니다")
    elif "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(f"'{option}'" for option in schema["enum"])
        problems.append(f"{path}: {allowed} 중 하나여야 합니다")
    elif not value.strip() and path.rsplit(".", 1)[-1] not in MAY_BE_EMPTY:
        problems.append(f"{path}: 비어 있습니다")
    elif PLACEHOLDER.search(value):
        problems.append(f"{path}: 채워지지 않은 자리표시가 있습니다")


def _items(
    content: dict[str, Any], chapter: str, field: str
) -> Iterator[tuple[str, Any]]:
    section = content.get(chapter)
    entries = section.get(field) if isinstance(section, dict) else None
    if isinstance(entries, list):
        for index, item in enumerate(entries):
            if isinstance(item, dict):
                yield f"{ROOT}.{chapter}.{field}[{index}]", item


def _check_references(
    content: dict[str, Any], files: Sequence[PromptFile]
) -> list[str]:
    lines = {file.path: count_lines(file.content) for file in files}
    problems: list[str] = []
    for path, item in _items(content, "chapter3", "file_breakdown"):
        if isinstance(item.get("file_path"), str) and item["file_path"] not in lines:
            problems.append(f"{path}: 올린 파일이 아닙니다 ({item['file_path']})")
    for path, item in _items(content, "chapter4", "explanations"):
        problems += _check_lines(path, item, lines)
    return problems


def _is_int(value: Any) -> TypeGuard[int]:
    # bool is a subclass of int in Python, but true/false is not a number.
    return isinstance(value, int) and not isinstance(value, bool)


def _check_lines(path: str, item: dict[str, Any], lines: dict[str, int]) -> list[str]:
    file_path, start, end = (
        item.get(k) for k in ("file_path", "line_start", "line_end")
    )
    if not (isinstance(file_path, str) and _is_int(start) and _is_int(end)):
        return []  # the shape check already reported it
    if file_path not in lines:
        return [f"{path}: 올린 파일이 아닙니다 ({file_path})"]
    total = lines[file_path]
    if not 1 <= start <= end <= total:
        return [f"{path}: {file_path}에는 1~{total}번째 줄만 있습니다 ({start}~{end})"]
    return []

"""JSON Schema of the 7-chapter learning document (spec.md FR-027 to FR-034).

Passed to GeminiClient.generate_json so every answer has the same shape
(FR-039). Chapter keys match the learning_documents content check (T090).
"""

from typing import Any

CHAPTER_TITLES: dict[str, str] = {
    "chapter1": "이 코드가 하는 일",
    "chapter2": "미리 알아둘 개념",
    "chapter3": "코드 구조 한눈에 보기",
    "chapter4": "한 줄씩 살펴보기",
    "chapter5": "실행 흐름 따라가기",
    "chapter6": "핵심 개념 정리",
    "chapter7": "자주 하는 실수",
}


def _text(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _int(description: str) -> dict[str, Any]:
    return {"type": "integer", "description": description}


def _object(**fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def _list(item: dict[str, Any], low: int, high: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "array", "items": item, "minItems": low}
    if high is not None:
        schema["maxItems"] = high
    return schema


def _chapter(key: str, **fields: dict[str, Any]) -> dict[str, Any]:
    return _object(title={"type": "string", "enum": [CHAPTER_TITLES[key]]}, **fields)


DOCUMENT_SCHEMA: dict[str, Any] = _object(
    chapter1=_chapter(
        "chapter1",
        summary=_text("전문 용어 없이 코드가 하는 일을 한 문장으로"),
    ),
    chapter2=_chapter(
        "chapter2",
        concepts=_list(
            _object(
                name=_text("개념 이름"),
                explanation=_text("쉬운 말 설명"),
                analogy=_text("일상생활 비유"),
                example=_text("짧은 코드 예시"),
                use_cases=_text("자주 쓰이는 곳"),
            ),
            1,
            5,
        ),
    ),
    chapter3=_chapter(
        "chapter3",
        flowchart=_text("실행 흐름을 나타내는 Mermaid flowchart 코드"),
        file_breakdown=_list(
            _object(
                file_path=_text("코드에 적힌 파일 경로 그대로"),
                role=_text("이 파일이 맡은 일"),
            ),
            1,
        ),
    ),
    chapter4=_chapter(
        "chapter4",
        explanations=_list(
            _object(
                file_path=_text("설명하는 줄이 있는 파일 경로"),
                line_start=_int("시작 줄 번호(코드 앞의 번호)"),
                line_end=_int("끝 줄 번호, 한 줄이면 시작과 같음"),
                code=_text("설명하는 코드 원문"),
                what_it_does=_text("이 줄이 하는 일"),
                syntax_breakdown=_text("기호와 단어를 하나씩 풀어 설명"),
                analogy=_text("일상생활 비유"),
                alternative_example=_text("같은 일을 하는 다른 코드 예시"),
                notes=_text("주의할 점, 없으면 빈 문자열"),
            ),
            1,
        ),
    ),
    chapter5=_chapter(
        "chapter5",
        steps=_list(
            _object(
                step=_int("1부터 시작하는 단계 번호"),
                description=_text("이 단계에서 일어나는 일"),
                data_state=_text("이 단계가 끝난 뒤 변수와 값, 예: result = 3"),
            ),
            1,
        ),
    ),
    chapter6=_chapter(
        "chapter6",
        concepts=_list(
            _object(
                name=_text("개념 이름"),
                what_it_is=_text("무엇인가"),
                why_used=_text("왜 쓰는가"),
                where_applied=_text("어디에 쓰는가"),
            ),
            1,
        ),
    ),
    chapter7=_chapter(
        "chapter7",
        mistakes=_list(
            _object(
                wrong=_text("틀린 코드 예시"),
                right=_text("고친 코드 예시"),
                why=_text("왜 문제가 되는가"),
                fix=_text("고치는 방법"),
            ),
            3,
            5,
        ),
    ),
)

"""Verifies the checks run on a generated document before it is stored (T093)."""

import copy
import unittest
from typing import Any

from src.services.ai.document_schema import CHAPTER_TITLES
from src.services.ai.prompts import PromptFile
from src.services.document.document_validator import validate_document

FILES = [
    PromptFile("src/add.py", "python", "def add(a, b):\n    return a + b\n"),
    PromptFile("src/main.py", "python", "from add import add\nprint(add(2, 3))\n"),
]


def valid_content() -> dict[str, Any]:
    concept = {
        "name": "함수",
        "explanation": "일을 묶어 이름을 붙인 것",
        "analogy": "레시피 카드",
        "example": "def f(): pass",
        "use_cases": "같은 일을 여러 번 할 때",
    }
    mistake = {
        "wrong": "def add(a b)",
        "right": "def add(a, b)",
        "why": "쉼표",
        "fix": "쉼표 추가",
    }
    return {
        "chapter1": {
            "title": CHAPTER_TITLES["chapter1"],
            "summary": "두 수를 더합니다.",
        },
        "chapter2": {"title": CHAPTER_TITLES["chapter2"], "concepts": [concept]},
        "chapter3": {
            "title": CHAPTER_TITLES["chapter3"],
            "flowchart": "flowchart TD\n A --> B",
            "file_breakdown": [{"file_path": "src/add.py", "role": "더하기 함수"}],
        },
        "chapter4": {
            "title": CHAPTER_TITLES["chapter4"],
            "explanations": [
                {
                    "file_path": "src/add.py",
                    "line_start": 1,
                    "line_end": 2,
                    "code": "def add(a, b):\n    return a + b",
                    "what_it_does": "더하기 함수를 만든다",
                    "syntax_breakdown": "def는 함수를 만든다는 뜻",
                    "analogy": "계산기 버튼",
                    "alternative_example": "lambda a, b: a + b",
                    "notes": "",
                }
            ],
        },
        "chapter5": {
            "title": CHAPTER_TITLES["chapter5"],
            "steps": [
                {
                    "step": 1,
                    "description": "add(2, 3) 호출",
                    "data_state": "a = 2, b = 3",
                }
            ],
        },
        "chapter6": {
            "title": CHAPTER_TITLES["chapter6"],
            "concepts": [
                {
                    "name": "함수",
                    "what_it_is": "묶음",
                    "why_used": "재사용",
                    "where_applied": "어디나",
                }
            ],
        },
        "chapter7": {"title": CHAPTER_TITLES["chapter7"], "mistakes": [mistake] * 3},
    }


def problems_for(content: Any) -> list[str]:
    return validate_document(content, FILES)


class TestValidDocument(unittest.TestCase):
    def test_valid_document_has_no_problems(self) -> None:
        self.assertEqual(problems_for(valid_content()), [])

    def test_empty_notes_are_allowed(self) -> None:
        # "notes" may be empty when there is nothing to warn about.
        self.assertEqual(problems_for(valid_content()), [])

    def test_does_not_change_the_document(self) -> None:
        content = valid_content()
        before = copy.deepcopy(content)
        problems_for(content)
        self.assertEqual(content, before)


class TestStructure(unittest.TestCase):
    def test_not_an_object(self) -> None:
        self.assertEqual(problems_for(["chapter1"]), ["document: 객체여야 합니다"])

    def test_missing_chapter(self) -> None:
        content = valid_content()
        del content["chapter7"]
        self.assertIn("document.chapter7: 빠졌습니다", problems_for(content))

    def test_unexpected_key(self) -> None:
        content = valid_content()
        content["chapter8"] = {}
        self.assertIn(
            "document.chapter8: 정해지지 않은 항목입니다", problems_for(content)
        )

    def test_wrong_title(self) -> None:
        content = valid_content()
        content["chapter1"]["title"] = "요약"
        self.assertIn(
            "document.chapter1.title: '이 코드가 하는 일' 중 하나여야 합니다",
            problems_for(content),
        )

    def test_blank_text(self) -> None:
        content = valid_content()
        content["chapter1"]["summary"] = "   "
        self.assertIn("document.chapter1.summary: 비어 있습니다", problems_for(content))

    def test_wrong_types(self) -> None:
        content = valid_content()
        content["chapter2"]["concepts"] = "함수"
        content["chapter5"]["steps"][0]["step"] = "1"
        problems = problems_for(content)
        self.assertIn("document.chapter2.concepts: 목록이어야 합니다", problems)
        self.assertIn("document.chapter5.steps[0].step: 정수여야 합니다", problems)

    def test_boolean_is_not_an_integer(self) -> None:
        content = valid_content()
        content["chapter5"]["steps"][0]["step"] = True
        self.assertIn(
            "document.chapter5.steps[0].step: 정수여야 합니다", problems_for(content)
        )

    def test_missing_field_inside_a_list_item(self) -> None:
        content = valid_content()
        del content["chapter2"]["concepts"][0]["analogy"]
        self.assertIn(
            "document.chapter2.concepts[0].analogy: 빠졌습니다", problems_for(content)
        )


class TestCounts(unittest.TestCase):
    def test_too_many_concept_cards(self) -> None:  # FR-029
        content = valid_content()
        content["chapter2"]["concepts"] *= 6
        self.assertIn(
            "document.chapter2.concepts: 최대 5개입니다 (6개)", problems_for(content)
        )

    def test_too_few_mistakes(self) -> None:  # FR-034
        content = valid_content()
        content["chapter7"]["mistakes"] = content["chapter7"]["mistakes"][:2]
        self.assertIn(
            "document.chapter7.mistakes: 최소 3개입니다 (2개)", problems_for(content)
        )

    def test_empty_line_explanations(self) -> None:
        content = valid_content()
        content["chapter4"]["explanations"] = []
        self.assertIn(
            "document.chapter4.explanations: 최소 1개입니다 (0개)",
            problems_for(content),
        )


class TestCodeReferences(unittest.TestCase):
    def test_line_numbers_must_exist_in_the_file(self) -> None:
        content = valid_content()
        content["chapter4"]["explanations"][0]["line_end"] = 9
        self.assertIn(
            "document.chapter4.explanations[0]: "
            "src/add.py에는 1~2번째 줄만 있습니다 (1~9)",
            problems_for(content),
        )

    def test_start_must_not_come_after_end(self) -> None:
        content = valid_content()
        content["chapter4"]["explanations"][0]["line_start"] = 2
        content["chapter4"]["explanations"][0]["line_end"] = 1
        self.assertIn(
            "document.chapter4.explanations[0]: "
            "src/add.py에는 1~2번째 줄만 있습니다 (2~1)",
            problems_for(content),
        )

    def test_unknown_file_paths(self) -> None:
        content = valid_content()
        content["chapter4"]["explanations"][0]["file_path"] = "add.py"
        content["chapter3"]["file_breakdown"][0]["file_path"] = "other.py"
        problems = problems_for(content)
        self.assertIn(
            "document.chapter4.explanations[0]: 올린 파일이 아닙니다 (add.py)", problems
        )
        self.assertIn(
            "document.chapter3.file_breakdown[0]: 올린 파일이 아닙니다 (other.py)",
            problems,
        )

    def test_reference_checks_skip_items_with_wrong_types(self) -> None:
        content = valid_content()
        content["chapter4"]["explanations"][0]["line_start"] = "1"
        problems = problems_for(content)
        self.assertEqual(
            problems, ["document.chapter4.explanations[0].line_start: 정수여야 합니다"]
        )

    def test_reference_checks_skip_lists_and_items_of_the_wrong_shape(self) -> None:
        content = valid_content()
        content["chapter3"]["file_breakdown"] = "src/add.py"
        content["chapter4"]["explanations"] = ["1번째 줄"]
        self.assertEqual(
            problems_for(content),
            [
                "document.chapter3.file_breakdown: 목록이어야 합니다",
                "document.chapter4.explanations[0]: 객체여야 합니다",
            ],
        )


class TestText(unittest.TestCase):
    def test_text_field_holding_something_else(self) -> None:
        content = valid_content()
        content["chapter1"]["summary"] = 42
        self.assertEqual(
            problems_for(content), ["document.chapter1.summary: 글이어야 합니다"]
        )


class TestPlaceholders(unittest.TestCase):
    def test_leftover_placeholders_are_reported(self) -> None:  # FR-095
        for text in ("[TODO]", "여기에 설명 [GENERATE]", "[todo] 나중에"):
            with self.subTest(text=text):
                content = valid_content()
                content["chapter1"]["summary"] = text
                self.assertIn(
                    "document.chapter1.summary: 채워지지 않은 자리표시가 있습니다",
                    problems_for(content),
                )

    def test_ordinary_brackets_are_fine(self) -> None:
        content = valid_content()
        content["chapter1"]["summary"] = "리스트 [1, 2, 3]의 합을 구합니다."
        self.assertEqual(problems_for(content), [])

"""Verifies TaskService input rules without a database (T068)."""

import unittest

from src.api.error_messages import TASK_MESSAGES
from src.api.exceptions import FieldValidationError, ForbiddenError, NotFoundError
from src.services.task_service import (
    TaskDraft,
    TaskForbiddenError,
    TaskNotFoundError,
    clean_description,
    clean_draft,
    clean_title,
)


def field_error(call: object) -> tuple[str, str]:
    assert callable(call)
    with unittest.TestCase().assertRaises(FieldValidationError) as caught:
        call()
    assert caught.exception.details is not None
    (item,) = caught.exception.details["fields"]
    return item["field"], item["message"]


class TestMessages(unittest.TestCase):
    def test_texts_follow_the_contract(self) -> None:
        self.assertEqual(
            TASK_MESSAGES["title_too_short"],
            "태스크 제목은 최소 5자 이상이어야 합니다.",
        )
        self.assertEqual(
            TASK_MESSAGES["title_too_long"],
            "태스크 제목은 최대 255자까지 입력할 수 있습니다.",
        )
        self.assertEqual(
            TASK_MESSAGES["description_too_long"],
            "태스크 설명은 최대 500자까지 입력할 수 있습니다.",
        )

    def test_errors_are_404_and_403_with_the_task_text(self) -> None:
        self.assertIsInstance(TaskNotFoundError(), NotFoundError)
        self.assertEqual(TaskNotFoundError().message, TASK_MESSAGES["not_found"])
        self.assertIsInstance(TaskForbiddenError(), ForbiddenError)
        self.assertEqual(TaskForbiddenError().message, TASK_MESSAGES["forbidden"])


class TestCleanTitle(unittest.TestCase):
    def test_trims_surrounding_whitespace(self) -> None:
        self.assertEqual(clean_title("  할 일 추가  "), "할 일 추가")

    def test_under_five_characters_after_trimming_is_rejected(self) -> None:
        for title in ("", "    ", "abcd", "  abcd  ", "가나다라"):
            with self.subTest(title=repr(title)):
                self.assertEqual(
                    field_error(lambda t=title: clean_title(t)),
                    ("title", TASK_MESSAGES["title_too_short"]),
                )

    def test_exactly_five_and_255_characters_are_allowed(self) -> None:
        self.assertEqual(clean_title("가" * 5), "가" * 5)
        self.assertEqual(clean_title("가" * 255), "가" * 255)

    def test_over_255_characters_is_rejected(self) -> None:
        self.assertEqual(
            field_error(lambda: clean_title("가" * 256)),
            ("title", TASK_MESSAGES["title_too_long"]),
        )


class TestCleanDescription(unittest.TestCase):
    def test_blank_or_missing_means_no_description(self) -> None:
        for value in (None, "", "   \n"):
            with self.subTest(value=value):
                self.assertIsNone(clean_description(value))

    def test_trims_and_allows_up_to_500_characters(self) -> None:
        self.assertEqual(clean_description("  설명  "), "설명")
        self.assertEqual(clean_description("가" * 500), "가" * 500)

    def test_over_500_characters_is_rejected(self) -> None:
        self.assertEqual(
            field_error(lambda: clean_description("가" * 501)),
            ("description", TASK_MESSAGES["description_too_long"]),
        )


class TestCleanDraft(unittest.TestCase):
    def test_returns_a_cleaned_copy(self) -> None:
        draft = clean_draft(TaskDraft("  제목입니다  ", " ", "file"))
        self.assertEqual(draft, TaskDraft("제목입니다", None, "file"))

    def test_accepts_every_upload_method(self) -> None:
        for method in ("file", "folder", "paste"):
            self.assertEqual(
                clean_draft(TaskDraft("제목입니다", None, method)).upload_method, method
            )

    def test_rejects_an_unknown_upload_method(self) -> None:
        for method in ("", "zip", "FILE"):
            with self.subTest(method=method):
                self.assertEqual(
                    field_error(
                        lambda m=method: clean_draft(TaskDraft("제목입니다", None, m))
                    ),
                    ("upload_method", TASK_MESSAGES["upload_method_invalid"]),
                )

    def test_title_is_checked_before_the_upload_method(self) -> None:
        self.assertEqual(
            field_error(lambda: clean_draft(TaskDraft("x", None, "zip")))[0], "title"
        )

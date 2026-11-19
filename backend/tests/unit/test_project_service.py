"""Verifies ProjectService input rules without a database (T044)."""

import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from src.api.error_messages import PROJECT_MESSAGES
from src.api.exceptions import FieldValidationError, NotFoundError
from src.services.project_service import ProjectNotFoundError, ProjectService

USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestMessages(unittest.TestCase):
    def test_texts_follow_chk084(self) -> None:
        self.assertEqual(
            PROJECT_MESSAGES["title_required"],
            "프로젝트 제목은 최소 1자 이상이어야 합니다.",
        )
        self.assertEqual(
            PROJECT_MESSAGES["not_found"],
            "요청한 프로젝트를 찾을 수 없습니다. "
            "삭제되었거나 존재하지 않는 프로젝트입니다.",
        )

    def test_not_found_error_is_a_404_with_the_project_text(self) -> None:
        error = ProjectNotFoundError()
        self.assertIsInstance(error, NotFoundError)
        self.assertEqual(error.status_code, 404)
        self.assertEqual(error.message, PROJECT_MESSAGES["not_found"])


class TestCreateValidation(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.session = MagicMock()
        self.session.commit = AsyncMock()
        self.service = ProjectService(self.session)

    async def assert_title_rejected(self, title: str, message: str) -> None:
        with self.assertRaises(FieldValidationError) as caught:
            await self.service.create(USER_ID, title)
        assert caught.exception.details is not None
        self.assertEqual(
            caught.exception.details["fields"],
            [{"field": "title", "message": message}],
        )
        self.session.add.assert_not_called()

    async def test_empty_title_is_rejected(self) -> None:
        for title in ("", "   ", "\t\n"):
            with self.subTest(title=repr(title)):
                await self.assert_title_rejected(
                    title, PROJECT_MESSAGES["title_required"]
                )

    async def test_title_over_255_characters_is_rejected(self) -> None:
        await self.assert_title_rejected("가" * 256, PROJECT_MESSAGES["title_too_long"])

    async def test_title_of_exactly_255_characters_is_allowed(self) -> None:
        project = await self.service.create(USER_ID, "가" * 255)
        self.assertEqual(len(project.title), 255)

    async def test_title_and_description_are_trimmed(self) -> None:
        project = await self.service.create(USER_ID, "  My Todo App ", "  할 일 앱  ")
        self.assertEqual(project.title, "My Todo App")
        self.assertEqual(project.description, "할 일 앱")
        self.assertEqual(project.user_id, USER_ID)

    async def test_blank_description_is_stored_as_none(self) -> None:
        project = await self.service.create(USER_ID, "제목", "   ")
        self.assertIsNone(project.description)

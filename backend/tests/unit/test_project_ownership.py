"""Verifies the project ownership error (T045)."""

import unittest

from src.api.error_messages import PROJECT_MESSAGES
from src.api.exceptions import ForbiddenError
from src.services.project_service import ProjectForbiddenError


class TestProjectForbiddenError(unittest.TestCase):
    def test_is_a_403_with_the_chk084_text(self) -> None:
        error = ProjectForbiddenError()
        self.assertIsInstance(error, ForbiddenError)
        self.assertEqual(error.status_code, 403)
        self.assertEqual(error.message, "이 프로젝트에 접근할 권한이 없습니다.")
        self.assertEqual(error.message, PROJECT_MESSAGES["forbidden"])

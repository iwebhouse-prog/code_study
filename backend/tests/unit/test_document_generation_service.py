"""Verifies document generation with retries, using a fake Gemini client (T093)."""

import logging
import unittest
from collections.abc import Mapping
from typing import Any

from src.services.ai.document_schema import DOCUMENT_SCHEMA
from src.services.ai.gemini_client import (
    AIBlockedError,
    AIInvalidResponseError,
    AIRequestError,
    AIServiceUnavailableError,
    AITimeoutError,
)
from src.services.ai.prompts import (
    DOCUMENT_SYSTEM_INSTRUCTION,
    build_document_prompt,
)
from src.services.document.document_generation_service import (
    BASE_DELAY_SECONDS,
    MAX_CONTENT_RETRIES,
    MAX_SERVICE_RETRIES,
    DocumentGenerationError,
    DocumentGenerationService,
)
from tests.unit.test_document_validator import FILES, valid_content


def invalid_content() -> dict[str, Any]:
    content = valid_content()
    content["chapter7"]["mistakes"] = content["chapter7"]["mistakes"][:2]
    return content


class FakeClient:
    """Plays back a script of answers (dicts) and errors, recording each call."""

    def __init__(self, *script: object) -> None:
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: str,
        schema: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "prompt": prompt,
                "system_instruction": system_instruction,
                "schema": schema,
            }
        )
        result = self.script.pop(0)
        if isinstance(result, BaseException):
            raise result
        assert isinstance(result, dict)
        return result


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def service_with(
    *script: object,
) -> tuple[DocumentGenerationService, FakeClient, Sleeps]:
    client, sleeps = FakeClient(*script), Sleeps()
    return DocumentGenerationService(client, sleep=sleeps), client, sleeps


async def generate(service: DocumentGenerationService) -> dict[str, Any]:
    return await service.generate(FILES, language="python", complexity="beginner")


class TestPolicy(unittest.TestCase):
    def test_retry_limits(self) -> None:
        # research.md §3: exponential backoff, up to 3 retries.
        self.assertEqual(MAX_SERVICE_RETRIES, 3)
        self.assertEqual(BASE_DELAY_SECONDS, 2)
        # FR-096: retry with a modified prompt up to 2 times.
        self.assertEqual(MAX_CONTENT_RETRIES, 2)


class TestSuccess(unittest.IsolatedAsyncioTestCase):
    async def test_first_answer_is_returned(self) -> None:
        service, client, sleeps = service_with(valid_content())
        self.assertEqual(await generate(service), valid_content())
        self.assertEqual(sleeps.delays, [])
        call = client.calls[0]
        self.assertEqual(
            call["prompt"],
            build_document_prompt(FILES, language="python", complexity="beginner"),
        )
        self.assertEqual(call["system_instruction"], DOCUMENT_SYSTEM_INSTRUCTION)
        self.assertEqual(call["schema"], DOCUMENT_SCHEMA)

    async def test_logs_success_with_attempt_count(self) -> None:
        service, _, _ = service_with(AITimeoutError("t"), valid_content())
        with self.assertLogs(
            "src.services.document.document_generation_service", logging.INFO
        ) as logs:
            await generate(service)
        self.assertIn("document_generated attempts=2", logs.output[-1])


class TestServiceRetries(unittest.IsolatedAsyncioTestCase):
    async def test_temporary_failures_back_off_exponentially(self) -> None:
        service, client, sleeps = service_with(
            AITimeoutError("t"),
            AIServiceUnavailableError("503"),
            AIInvalidResponseError("broken json"),
            valid_content(),
        )
        self.assertEqual(await generate(service), valid_content())
        self.assertEqual(sleeps.delays, [2, 4, 8])
        self.assertEqual(len(client.calls), 4)

    async def test_gives_up_after_three_retries(self) -> None:
        service, client, sleeps = service_with(*[AITimeoutError("t")] * 4)
        with self.assertRaises(DocumentGenerationError) as caught:
            await generate(service)
        self.assertEqual(caught.exception.reason, "ai_unavailable")
        self.assertEqual(caught.exception.attempts, 4)
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(sleeps.delays, [2, 4, 8])
        self.assertIsInstance(caught.exception.__cause__, AITimeoutError)

    async def test_hopeless_errors_are_not_retried(self) -> None:
        for error in (AIRequestError("400"), AIBlockedError("safety")):
            with self.subTest(error=type(error).__name__):
                service, client, sleeps = service_with(error)
                with self.assertRaises(DocumentGenerationError) as caught:
                    await generate(service)
                self.assertEqual(caught.exception.reason, "ai_rejected")
                self.assertEqual(len(client.calls), 1)
                self.assertEqual(sleeps.delays, [])

    async def test_failures_are_logged(self) -> None:
        service, _, _ = service_with(AIRequestError("400"))
        with (
            self.assertLogs(
                "src.services.document.document_generation_service", logging.WARNING
            ) as logs,
            self.assertRaises(DocumentGenerationError),
        ):
            await generate(service)
        self.assertIn("document_generation_failed reason=ai_rejected", logs.output[-1])


class TestContentRetries(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_document_is_asked_for_again_with_its_problems(self) -> None:
        service, client, sleeps = service_with(invalid_content(), valid_content())
        self.assertEqual(await generate(service), valid_content())
        retry_prompt = client.calls[1]["prompt"]
        self.assertTrue(retry_prompt.startswith(client.calls[0]["prompt"]))
        self.assertIn("document.chapter7.mistakes: 최소 3개입니다 (2개)", retry_prompt)
        self.assertEqual(sleeps.delays, [])  # nothing to wait for

    async def test_gives_up_after_two_content_retries(self) -> None:
        service, client, _ = service_with(*[invalid_content()] * 3)
        with self.assertRaises(DocumentGenerationError) as caught:
            await generate(service)
        error = caught.exception
        self.assertEqual(error.reason, "invalid_content")
        self.assertEqual(error.attempts, 3)
        self.assertIn(
            "document.chapter7.mistakes: 최소 3개입니다 (2개)", error.problems
        )
        self.assertEqual(len(client.calls), 3)

    async def test_the_two_retry_budgets_are_separate(self) -> None:
        # A timeout while re-asking does not use up a content retry, and the
        # re-asked prompt is the one sent again after the wait.
        service, client, sleeps = service_with(
            invalid_content(), AITimeoutError("t"), valid_content()
        )
        self.assertEqual(await generate(service), valid_content())
        self.assertEqual(sleeps.delays, [2])
        self.assertEqual(client.calls[2]["prompt"], client.calls[1]["prompt"])

    async def test_service_retries_count_across_content_retries(self) -> None:
        service, _, _ = service_with(
            AITimeoutError("t"),
            invalid_content(),
            AITimeoutError("t"),
            AITimeoutError("t"),
            AITimeoutError("t"),
        )
        with self.assertRaises(DocumentGenerationError) as caught:
            await generate(service)
        self.assertEqual(caught.exception.reason, "ai_unavailable")
        self.assertEqual(caught.exception.attempts, 5)


class TestErrorMessage(unittest.TestCase):
    def test_message_names_reason_and_attempts(self) -> None:
        error = DocumentGenerationError(
            "invalid_content", attempts=3, problems=["a", "b"]
        )
        self.assertIn("invalid_content", str(error))
        self.assertIn("3", str(error))
        self.assertIn("a", str(error))

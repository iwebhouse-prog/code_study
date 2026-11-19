"""Verifies the Gemini API wrapper without calling the real API (T091)."""

import asyncio
import logging
import unittest
from typing import Any

import httpx
from google.genai import errors, types

from src.services.ai.gemini_client import (
    DEFAULT_MODEL,
    DOCUMENT_TIMEOUT_SECONDS,
    QA_TIMEOUT_SECONDS,
    AIBlockedError,
    AIInvalidResponseError,
    AIRateLimitError,
    AIRequestError,
    AIServiceError,
    AIServiceUnavailableError,
    AITimeoutError,
    GeminiClient,
    GeminiConfig,
)

KEY = "AIza" + "x" * 35
ENV = {"GOOGLE_API_KEY": KEY, "GEMINI_MODEL": "gemini-test-model"}


def response(
    text: str | None = "안녕하세요",
    finish: types.FinishReason = types.FinishReason.STOP,
    block: types.BlockedReason | None = None,
) -> types.GenerateContentResponse:
    parts = [types.Part(text=text)] if text is not None else []
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts), finish_reason=finish
            )
        ],
        prompt_feedback=(
            types.GenerateContentResponsePromptFeedback(block_reason=block)
            if block
            else None
        ),
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=12, candidates_token_count=7
        ),
    )


class FakeModels:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        if isinstance(self.result, BaseException):
            raise self.result
        if callable(self.result):
            return await self.result()  # type: ignore[no-any-return]
        assert isinstance(self.result, types.GenerateContentResponse)
        return self.result


class FakeGenai:
    def __init__(self, result: object) -> None:
        self.models = FakeModels(result)
        self.aio = self


def client_with(result: object) -> tuple[GeminiClient, FakeModels]:
    fake = FakeGenai(result)
    return GeminiClient(GeminiConfig.from_env(ENV), client=fake), fake.models


def api_error(cls: type[errors.APIError], code: int) -> errors.APIError:
    return cls(code, {"error": {"code": code, "message": "x", "status": "X"}})


class TestGeminiConfig(unittest.TestCase):
    def test_reads_key_and_model(self) -> None:
        config = GeminiConfig.from_env(ENV)
        self.assertEqual((config.api_key, config.model), (KEY, "gemini-test-model"))

    def test_model_defaults_to_research_choice(self) -> None:
        self.assertEqual(DEFAULT_MODEL, "gemini-3-flash-preview")
        for env in (
            {"GOOGLE_API_KEY": KEY},
            {"GOOGLE_API_KEY": KEY, "GEMINI_MODEL": " "},
        ):
            with self.subTest(env=env):
                self.assertEqual(GeminiConfig.from_env(env).model, DEFAULT_MODEL)

    def test_missing_key_is_refused(self) -> None:
        for env in ({}, {"GOOGLE_API_KEY": ""}, {"GOOGLE_API_KEY": "  "}):
            with (
                self.subTest(env=env),
                self.assertRaisesRegex(RuntimeError, "GOOGLE_API_KEY is not set"),
            ):
                GeminiConfig.from_env(env)

    def test_placeholder_key_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "placeholder"):
            GeminiConfig.from_env({"GOOGLE_API_KEY": "change-me-google-api-key"})

    def test_key_never_appears_in_repr(self) -> None:
        config = GeminiConfig.from_env(ENV)
        self.assertNotIn(KEY, repr(config))
        self.assertNotIn(KEY, repr(GeminiClient(config, client=FakeGenai(response()))))

    def test_real_sdk_client_is_built_from_the_config(self) -> None:
        client = GeminiClient(GeminiConfig.from_env(ENV))
        self.assertEqual(client.model, "gemini-test-model")


class TestTimeouts(unittest.TestCase):
    def test_research_timeouts(self) -> None:
        # research.md §3: 20s for Q&A, 3 minutes for documents.
        self.assertEqual(QA_TIMEOUT_SECONDS, 20)
        self.assertEqual(DOCUMENT_TIMEOUT_SECONDS, 180)


class TestGenerateText(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_text_and_sends_model_prompt_and_instruction(
        self,
    ) -> None:
        client, models = client_with(response("변수는 이름표입니다."))
        text = await client.generate_text("변수가 뭐예요?", system_instruction="선생님")
        self.assertEqual(text, "변수는 이름표입니다.")
        call = models.calls[0]
        self.assertEqual(call["model"], "gemini-test-model")
        self.assertEqual(call["contents"], "변수가 뭐예요?")
        self.assertEqual(call["config"].system_instruction, "선생님")
        self.assertIsNone(call["config"].response_mime_type)

    async def test_logs_the_call_without_prompt_or_key(self) -> None:
        client, _ = client_with(response())
        with self.assertLogs("src.services.ai.gemini_client", logging.INFO) as logs:
            await client.generate_text("비밀 프롬프트", system_instruction="s")
        line = logs.output[0]
        self.assertIn("gemini_call", line)
        self.assertIn("outcome=ok", line)
        self.assertIn("prompt_tokens=12", line)
        self.assertIn("output_tokens=7", line)
        self.assertNotIn("비밀 프롬프트", line)
        self.assertNotIn(KEY, line)

    async def test_empty_answer_is_an_invalid_response(self) -> None:
        for result in (response(text=None), response(text="  ")):
            client, _ = client_with(result)
            with self.assertRaises(AIInvalidResponseError) as caught:
                await client.generate_text("q", system_instruction="s")
            self.assertTrue(caught.exception.retryable)


class TestGenerateJson(unittest.IsolatedAsyncioTestCase):
    async def test_parses_the_json_object_and_asks_for_json(self) -> None:
        client, models = client_with(response('{"chapter1": {"title": "요약"}}'))
        schema = {"type": "object"}
        data = await client.generate_json("코드", system_instruction="s", schema=schema)
        self.assertEqual(data, {"chapter1": {"title": "요약"}})
        config = models.calls[0]["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.response_json_schema, schema)

    async def test_schema_is_optional(self) -> None:
        client, models = client_with(response("{}"))
        self.assertEqual(await client.generate_json("코드", system_instruction="s"), {})
        self.assertIsNone(models.calls[0]["config"].response_json_schema)

    async def test_broken_or_non_object_json_is_an_invalid_response(self) -> None:
        for text in ('{"chapter1": ', "[1, 2]", "그냥 글"):
            with self.subTest(text=text):
                client, _ = client_with(response(text))
                with self.assertRaises(AIInvalidResponseError) as caught:
                    await client.generate_json("코드", system_instruction="s")
                self.assertTrue(caught.exception.retryable)

    async def test_answer_cut_off_by_the_token_limit_is_retryable(self) -> None:
        client, _ = client_with(
            response('{"a": 1', finish=types.FinishReason.MAX_TOKENS)
        )
        with self.assertRaises(AIInvalidResponseError):
            await client.generate_json("코드", system_instruction="s")


class TestErrors(unittest.IsolatedAsyncioTestCase):
    async def _raises(self, result: object) -> AIServiceError:
        client, _ = client_with(result)
        with self.assertRaises(AIServiceError) as caught:
            await client.generate_text("q", system_instruction="s", timeout=0.05)
        return caught.exception

    async def test_rate_limit_is_retryable(self) -> None:
        error = await self._raises(api_error(errors.ClientError, 429))
        self.assertIsInstance(error, AIRateLimitError)
        self.assertTrue(error.retryable)

    async def test_server_errors_are_retryable(self) -> None:
        for code in (500, 503):
            with self.subTest(code=code):
                error = await self._raises(api_error(errors.ServerError, code))
                self.assertIsInstance(error, AIServiceUnavailableError)
                self.assertTrue(error.retryable)

    async def test_network_failure_is_retryable(self) -> None:
        error = await self._raises(httpx.ConnectError("no route"))
        self.assertIsInstance(error, AIServiceUnavailableError)

    async def test_other_api_errors_count_as_unavailable(self) -> None:
        error = await self._raises(api_error(errors.APIError, 302))
        self.assertIsInstance(error, AIServiceUnavailableError)

    async def test_bad_request_or_bad_key_is_not_retryable(self) -> None:
        for code in (400, 401, 403, 404):
            with self.subTest(code=code):
                error = await self._raises(api_error(errors.ClientError, code))
                self.assertIsInstance(error, AIRequestError)
                self.assertFalse(error.retryable)
                self.assertIn(str(code), str(error))

    async def test_slow_answer_times_out(self) -> None:
        async def slow() -> types.GenerateContentResponse:
            await asyncio.sleep(1)
            return response()

        error = await self._raises(slow)
        self.assertIsInstance(error, AITimeoutError)
        self.assertTrue(error.retryable)

    async def test_blocked_prompt_is_not_retryable(self) -> None:
        error = await self._raises(
            response(text=None, block=types.BlockedReason.SAFETY)
        )
        self.assertIsInstance(error, AIBlockedError)
        self.assertFalse(error.retryable)

    async def test_answer_stopped_for_safety_is_blocked(self) -> None:
        error = await self._raises(
            response(text=None, finish=types.FinishReason.SAFETY)
        )
        self.assertIsInstance(error, AIBlockedError)

    async def test_failures_are_logged_with_their_outcome(self) -> None:
        client, _ = client_with(api_error(errors.ServerError, 503))
        with (
            self.assertLogs("src.services.ai.gemini_client", logging.WARNING) as logs,
            self.assertRaises(AIServiceUnavailableError),
        ):
            await client.generate_text("q", system_instruction="s")
        self.assertIn("outcome=AIServiceUnavailableError", logs.output[0])

    async def test_unexpected_errors_are_not_hidden(self) -> None:
        client, _ = client_with(KeyError("bug"))
        with self.assertRaises(KeyError):
            await client.generate_text("q", system_instruction="s")

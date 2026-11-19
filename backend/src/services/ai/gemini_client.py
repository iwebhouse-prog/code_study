"""Thin wrapper around the Gemini API (research.md §3).

It sends one request, enforces a timeout, and turns every failure into an
AIServiceError that says whether trying again may help (`retryable`). Retrying
itself belongs to DocumentGenerationService (T093). Each call is logged with
its model, duration, token counts and outcome; prompts and the key never are.
"""

import asyncio
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx
from google import genai
from google.genai import errors, types

from src.config import load_env

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3-flash-preview"
QA_TIMEOUT_SECONDS = 20
DOCUMENT_TIMEOUT_SECONDS = 180


class AIServiceError(Exception):
    retryable: ClassVar[bool] = False


class AITimeoutError(AIServiceError):
    retryable = True


class AIRateLimitError(AIServiceError):
    retryable = True


class AIServiceUnavailableError(AIServiceError):
    retryable = True


class AIInvalidResponseError(AIServiceError):
    """Empty, cut-off or unparsable answer; a new attempt usually differs."""

    retryable = True


class AIRequestError(AIServiceError):
    """The request itself is wrong (bad key, bad model, bad input)."""


class AIBlockedError(AIServiceError):
    """Safety filters stopped the prompt or the answer."""


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = field(repr=False)
    model: str = DEFAULT_MODEL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GeminiConfig":
        env = load_env(env)
        api_key = env.get("GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. "
                "Get a key at https://aistudio.google.com/apikey"
            )
        if api_key.startswith("change-me"):
            raise ValueError("GOOGLE_API_KEY still has the .env.example placeholder")
        model = env.get("GEMINI_MODEL", "").strip() or cls.model
        return cls(api_key=api_key, model=model)


class GeminiClient:
    def __init__(self, config: GeminiConfig, client: Any = None) -> None:
        self.model = config.model
        self._client = client or genai.Client(api_key=config.api_key)

    def __repr__(self) -> str:
        return f"<GeminiClient model={self.model}>"

    async def generate_text(
        self,
        prompt: str,
        *,
        system_instruction: str,
        timeout: float = QA_TIMEOUT_SECONDS,
    ) -> str:
        config = types.GenerateContentConfig(system_instruction=system_instruction)
        return await self._generate(prompt, config, timeout)

    async def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: str,
        schema: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Asks for JSON (optionally matching a JSON Schema) and parses it."""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_json_schema=dict(schema) if schema is not None else None,
        )
        text = await self._generate(prompt, config, DOCUMENT_TIMEOUT_SECONDS)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise AIInvalidResponseError(
                f"answer is not valid JSON: {error}"
            ) from error
        if not isinstance(data, dict):
            raise AIInvalidResponseError("answer is JSON but not an object")
        return data

    async def _generate(
        self, prompt: str, config: types.GenerateContentConfig, timeout: float
    ) -> str:
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                ),
                timeout,
            )
            text = _answer_text(response)
        except AIServiceError as error:
            self._log(started, type(error).__name__, logging.WARNING)
            raise
        except (TimeoutError, errors.APIError, httpx.TransportError) as error:
            translated = _translate(error, timeout)
            self._log(started, type(translated).__name__, logging.WARNING)
            raise translated from error
        self._log(started, "ok", logging.INFO, response.usage_metadata)
        return text

    def _log(
        self,
        started: float,
        outcome: str,
        level: int,
        usage: types.GenerateContentResponseUsageMetadata | None = None,
    ) -> None:
        logger.log(
            level,
            "gemini_call model=%s duration_ms=%d outcome=%s "
            "prompt_tokens=%s output_tokens=%s",
            self.model,
            (time.perf_counter() - started) * 1000,
            outcome,
            usage.prompt_token_count if usage else None,
            usage.candidates_token_count if usage else None,
        )


def _answer_text(response: types.GenerateContentResponse) -> str:
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason is not None:
        raise AIBlockedError(f"prompt blocked: {feedback.block_reason}")
    candidates = response.candidates or []
    if candidates and candidates[0].finish_reason == types.FinishReason.SAFETY:
        raise AIBlockedError("answer blocked by safety filters")
    text = response.text
    if text is None or not text.strip():
        raise AIInvalidResponseError("answer is empty")
    return text


def _translate(error: Exception, timeout: float) -> AIServiceError:
    if isinstance(error, TimeoutError):
        return AITimeoutError(f"no answer within {timeout:g} seconds")
    if isinstance(error, errors.ClientError):
        if error.code == 429:
            return AIRateLimitError("Gemini rate limit or quota reached (429)")
        return AIRequestError(f"Gemini rejected the request ({error.code})")
    return AIServiceUnavailableError(f"Gemini is unavailable: {error}")

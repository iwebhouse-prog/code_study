"""Generates one learning document with retries (T093).

Two separate retry budgets:
- service failures the client marks retryable (timeout, 429, 5xx, broken
  JSON): exponential backoff 2s, 4s, 8s, at most 3 retries (research.md §3);
- a document that fails validation: ask again with its problems appended, at
  most 2 times (FR-096 "retry with modified prompt").
Failures the client marks hopeless (bad key, blocked by safety) stop at once.

The service does not touch the database: the Celery task (T094) records the
generation status around it.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol

from src.services.ai.document_schema import DOCUMENT_SCHEMA
from src.services.ai.gemini_client import AIServiceError
from src.services.ai.prompts import (
    DOCUMENT_SYSTEM_INSTRUCTION,
    PromptFile,
    build_document_prompt,
    build_retry_prompt,
)
from src.services.document.document_validator import validate_document

logger = logging.getLogger(__name__)

MAX_SERVICE_RETRIES = 3
BASE_DELAY_SECONDS = 2
MAX_CONTENT_RETRIES = 2


class JsonGenerator(Protocol):
    async def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: str,
        schema: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class DocumentGenerationError(Exception):
    """reason: ai_rejected (hopeless), ai_unavailable (retries used up) or
    invalid_content (still invalid after re-asking)."""

    def __init__(
        self, reason: str, *, attempts: int, problems: Sequence[str] = ()
    ) -> None:
        self.reason = reason
        self.attempts = attempts
        self.problems = list(problems)
        detail = f": {'; '.join(self.problems)}" if self.problems else ""
        super().__init__(f"{reason} after {attempts} attempts{detail}")


class DocumentGenerationService:
    def __init__(
        self,
        client: JsonGenerator,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    async def generate(
        self,
        files: Sequence[PromptFile],
        *,
        language: str | None,
        complexity: str | None,
    ) -> dict[str, Any]:
        """A validated 7-chapter document, or DocumentGenerationError."""
        first_prompt = build_document_prompt(
            files, language=language, complexity=complexity
        )
        prompt = first_prompt
        attempts = service_retries = content_retries = 0
        while True:
            attempts += 1
            try:
                content = await self._client.generate_json(
                    prompt,
                    system_instruction=DOCUMENT_SYSTEM_INSTRUCTION,
                    schema=DOCUMENT_SCHEMA,
                )
            except AIServiceError as error:
                if not error.retryable or service_retries == MAX_SERVICE_RETRIES:
                    reason = "ai_unavailable" if error.retryable else "ai_rejected"
                    raise _failed(reason, attempts) from error
                await self._sleep(BASE_DELAY_SECONDS * 2**service_retries)
                service_retries += 1
                continue
            problems = validate_document(content, files)
            if not problems:
                logger.info("document_generated attempts=%d", attempts)
                return content
            if content_retries == MAX_CONTENT_RETRIES:
                raise _failed("invalid_content", attempts, problems)
            logger.info("document_content_retry problems=%d", len(problems))
            content_retries += 1
            prompt = build_retry_prompt(first_prompt, problems)


def _failed(
    reason: str, attempts: int, problems: Sequence[str] = ()
) -> DocumentGenerationError:
    logger.warning("document_generation_failed reason=%s attempts=%d", reason, attempts)
    return DocumentGenerationError(reason, attempts=attempts, problems=problems)

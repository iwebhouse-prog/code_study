"""Celery task that writes a task's learning document (T094, documents-api.md).

The worker process is synchronous, so the task runs its async work with
asyncio.run. Everything it needs (database, file storage, AI service) is built
by build_runtime() and handed to generate_for_task(), so tests can pass fakes.

The task never makes Celery retry: DocumentGenerationService already retried
the AI calls, and a failed document is retried by the user (regenerate).
"""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import AppConfig
from src.db.config import DatabaseConfig
from src.db.session import Database
from src.models import LearningDocument, Task, UploadedCode
from src.services.ai.gemini_client import GeminiClient, GeminiConfig
from src.services.ai.prompts import PromptFile
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.language_detector import detect_file_language
from src.services.document.document_generation_service import (
    DocumentGenerationError,
    DocumentGenerationService,
)
from src.tasks.celery_app import app

logger = logging.getLogger(__name__)

TASK_NAME = "src.tasks.document_generation.generate_document"
SKIP_STATUSES = ("completed", "in_progress")
MAX_ERROR_DETAIL = 500


class DocumentWriter(Protocol):
    async def generate(
        self,
        files: list[PromptFile],
        *,
        language: str | None,
        complexity: str | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class GenerationRuntime:
    database: Database
    storage: FileStorage
    writer: DocumentWriter = field(repr=False)


def build_runtime(env: Mapping[str, str] | None = None) -> GenerationRuntime:
    """Real services from the environment (.env); one set per task run."""
    db_config = DatabaseConfig.from_env(env)
    return GenerationRuntime(
        database=Database(db_config.url, **db_config.engine_options()),
        storage=FileStorage(AppConfig.from_env(env).upload_dir),
        writer=DocumentGenerationService(GeminiClient(GeminiConfig.from_env(env))),
    )


@app.task(bind=True, name=TASK_NAME, max_retries=0)
def generate_document(self: Any, task_id: str) -> str:
    """Returns "completed", "failed" or "skipped"; never raises for AI failures."""
    return asyncio.run(_run(task_id, str(self.request.id)))


async def _run(task_id: str, celery_task_id: str) -> str:
    runtime = build_runtime()
    try:
        return await generate_for_task(task_id, celery_task_id, runtime)
    finally:
        await runtime.database.dispose()


async def generate_for_task(
    task_id: str, celery_task_id: str, runtime: GenerationRuntime
) -> str:
    async with runtime.database.session() as session:
        task = await session.scalar(
            select(Task)
            .options(selectinload(Task.uploaded_code).selectinload(UploadedCode.files))
            .where(Task.id == task_id)
        )
        if task is None or task.uploaded_code is None:
            logger.warning("document_task_skipped task_id=%s reason=no_code", task_id)
            return "skipped"
        document = await session.scalar(
            select(LearningDocument).where(LearningDocument.task_id == task.id)
        )
        if document is None:
            document = LearningDocument(
                task_id=task.id,
                content=LearningDocument.empty_content(),
                generation_status="pending",
            )
            session.add(document)
        if document.generation_status in SKIP_STATUSES:
            return "skipped"
        document.start(celery_task_id)
        await session.commit()
        code = task.uploaded_code
        try:
            files = await asyncio.to_thread(_read_files, runtime.storage, code)
            content = await runtime.writer.generate(
                files, language=code.detected_language, complexity=code.complexity_level
            )
            if not await _still_ours(session, document, celery_task_id):
                return "skipped"
            document.complete(content)
            await session.commit()
        except Exception as error:  # noqa: BLE001 - every failure is recorded
            await session.rollback()
            await _record_failure(runtime.database, task.id, _describe(error))
            return "failed"
    return "completed"


async def _still_ours(
    session: AsyncSession, document: LearningDocument, celery_task_id: str
) -> bool:
    """Locks the row and checks this run still owns it.

    While the AI worked, the document may have been declared failed (stale) or
    restarted by the user; a late result must not overwrite that.
    """
    await session.refresh(document, with_for_update=True)
    ours = (
        document.generation_status == "in_progress"
        and document.celery_task_id == celery_task_id
    )
    if not ours:
        logger.warning("document_result_dropped task_id=%s", document.task_id)
        await session.rollback()
    return ours


def _read_files(storage: FileStorage, code: UploadedCode) -> list[PromptFile]:
    files = []
    for row in code.files:
        text = storage.read(row.storage_path)
        language = detect_file_language(row.file_name, text)
        files.append(PromptFile(row.file_path or row.file_name, language, text))
    return files


def _describe(error: Exception) -> str:
    """The text for generation_error: "<reason>: <english detail>"."""
    if isinstance(error, DocumentGenerationError):
        detail = f"after {error.attempts} attempts"
        if error.problems:
            detail += f": {'; '.join(error.problems)}"
        return f"{error.reason}: {detail}"[:MAX_ERROR_DETAIL]
    if isinstance(error, SoftTimeLimitExceeded):
        return "timeout: soft time limit of 270 seconds exceeded"
    logger.error("document_generation_failed", exc_info=error)
    return f"internal_error: {type(error).__name__}: {error}"[:MAX_ERROR_DETAIL]


async def _record_failure(database: Database, task_id: Any, error: str) -> None:
    """Marks the run failed in a fresh session (the old one just rolled back)."""
    async with database.session() as session:
        document = await session.scalar(
            select(LearningDocument).where(LearningDocument.task_id == task_id)
        )
        # A run already declared failed (stale) or restarted is left alone.
        if document is not None and document.generation_status == "in_progress":
            document.fail(error)
            await session.commit()

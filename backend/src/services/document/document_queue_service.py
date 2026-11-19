"""Queues document generation and reports its progress (T095, documents-api.md).

The API checks task ownership first (TaskService); every method here takes the
task id of a task the caller may already see.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.error_messages import DOCUMENT_MESSAGES
from src.api.exceptions import ConflictError, NotFoundError
from src.models import LearningDocument, UploadedCode
from src.tasks.document_generation import generate_document

logger = logging.getLogger(__name__)

ERROR_REASONS = ("ai_unavailable", "ai_rejected", "invalid_content", "timeout")
FALLBACK_REASON = "internal_error"  # also for any reason not listed above
MIN_TOTAL_SECONDS = 30
MAX_TOTAL_SECONDS = 180
SECONDS_PER_LINE = 0.3
MIN_REMAINING_SECONDS = 5


class DocumentNotFoundError(NotFoundError):
    error = "document_not_found"
    message = DOCUMENT_MESSAGES["document_not_found"]


class DocumentNotReadyError(ConflictError):
    error = "document_not_ready"
    message = DOCUMENT_MESSAGES["document_not_ready"]


class DocumentNotFailedError(ConflictError):
    error = "document_not_failed"
    message = DOCUMENT_MESSAGES["document_not_failed"]


@dataclass(frozen=True)
class DocumentStatus:
    """The contract's Status object; error_reason is a code, never the detail."""

    task_id: uuid.UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    estimated_seconds_remaining: int | None
    error_reason: str | None


def send_generation_task(task_id: str) -> None:
    # retry=False: with Redis down, fail at once instead of stalling the request.
    generate_document.apply_async(args=[task_id], retry=False)


def expected_seconds(total_lines: int) -> int:
    """FR-024: clamp(30 + 0.3 x lines, 30, 180) seconds for the whole run."""
    expected = MIN_TOTAL_SECONDS + SECONDS_PER_LINE * total_lines
    return round(min(max(expected, MIN_TOTAL_SECONDS), MAX_TOTAL_SECONDS))


class DocumentQueueService:
    def __init__(
        self,
        session: AsyncSession,
        send: Callable[[str], None] = send_generation_task,
    ) -> None:
        self.session = session
        self._send = send

    async def enqueue(self, task_id: uuid.UUID) -> None:
        """Creates the pending row if needed, commits, then queues the task.

        Never raises: the upload that triggered this has already succeeded, and
        a pending document can be queued again with regenerate.
        """
        try:
            await self._ensure_row(task_id)
            await self.session.commit()
        except Exception:
            logger.exception("document_row_failed task_id=%s", task_id)
            await self.session.rollback()
            return
        self._queue(task_id)

    async def status(
        self, task_id: uuid.UUID, now: datetime | None = None
    ) -> DocumentStatus:
        return await self._status_of(
            await self._document(task_id), now or datetime.now(UTC)
        )

    async def get_completed(
        self, task_id: uuid.UUID, now: datetime | None = None
    ) -> LearningDocument:
        document = await self._document(task_id)
        if not document.is_completed:
            shown = "failed" if document.is_stale(now) else document.generation_status
            raise DocumentNotReadyError(details={"status": shown})
        return document

    async def regenerate(
        self, task_id: uuid.UUID, now: datetime | None = None
    ) -> DocumentStatus:
        now = now or datetime.now(UTC)
        # Locked, so two quick clicks cannot both restart the same failure.
        document = await self._document(task_id, lock=True)
        if not document.can_restart(now):
            await self.session.rollback()
            raise DocumentNotFailedError()
        document.restart(now)
        await self.session.commit()
        self._queue(task_id)
        return await self._status_of(document, now)

    def _queue(self, task_id: uuid.UUID) -> None:
        try:
            self._send(str(task_id))
        except Exception:
            logger.exception("document_queue_failed task_id=%s", task_id)

    async def _ensure_row(self, task_id: uuid.UUID) -> None:
        existing = await self.session.scalar(
            select(LearningDocument.id).where(LearningDocument.task_id == task_id)
        )
        if existing is None:
            self.session.add(
                LearningDocument(
                    task_id=task_id,
                    content=LearningDocument.empty_content(),
                    generation_status="pending",
                )
            )

    async def _document(
        self, task_id: uuid.UUID, *, lock: bool = False
    ) -> LearningDocument:
        query = select(LearningDocument).where(LearningDocument.task_id == task_id)
        document = await self.session.scalar(query.with_for_update() if lock else query)
        if document is None:
            raise DocumentNotFoundError()
        return document

    async def _status_of(
        self, document: LearningDocument, now: datetime
    ) -> DocumentStatus:
        if document.is_stale(now):
            return DocumentStatus(
                document.task_id, "failed", None, None, None, "timeout"
            )
        remaining = None
        if document.generation_status in ("pending", "in_progress"):
            remaining = await self._remaining_seconds(document, now)
        return DocumentStatus(
            task_id=document.task_id,
            status=document.generation_status,
            started_at=document.generation_started_at,
            completed_at=document.generation_completed_at,
            estimated_seconds_remaining=remaining,
            error_reason=_reason_of(document),
        )

    async def _remaining_seconds(
        self, document: LearningDocument, now: datetime
    ) -> int:
        lines = await self.session.scalar(
            select(UploadedCode.total_lines).where(
                UploadedCode.task_id == document.task_id
            )
        )
        total = expected_seconds(lines or 0)
        started = document.generation_started_at
        if document.generation_status == "pending" or started is None:
            return total
        elapsed = (now - started).total_seconds()
        return max(round(total - elapsed), MIN_REMAINING_SECONDS)


def _reason_of(document: LearningDocument) -> str | None:
    if document.generation_status != "failed":
        return None
    reason = (document.generation_error or "").split(":", 1)[0].strip()
    return reason if reason in ERROR_REASONS else FALLBACK_REASON

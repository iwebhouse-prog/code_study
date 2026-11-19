"""Creates a task together with its uploaded code (T069, contracts/tasks-api.md).

The task row, the code rows and the files on disk are saved as one unit: if
anything fails after files were written, the database work is rolled back and
the written files are deleted.
"""

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CodeFile, Task, UploadedCode
from src.services.code_analysis.complexity_analyzer import (
    ComplexityReport,
    assess_complexity,
)
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.language_detector import detect_language
from src.services.code_analysis.upload_files import (
    IncomingFile,
    PastedCode,
    PreparedFile,
    prepare_files,
    prepare_pasted_code,
)
from src.services.task_service import TaskDraft, TaskService, clean_draft


class DocumentQueue(Protocol):
    async def enqueue(self, task_id: uuid.UUID) -> None: ...


@dataclass(frozen=True)
class UploadResult:
    """The new task (code and files loaded) and the excluded paths."""

    task: Task
    excluded_paths: list[str]


@dataclass(frozen=True)
class Analysis:
    language: str | None
    report: ComplexityReport


def analyze(files: Sequence[PreparedFile], chosen_language: str | None) -> Analysis:
    """Language (T065) and complexity (T066); CPU work, so run it in a thread."""
    pairs = [(file.file_path, file.text) for file in files]
    return Analysis(chosen_language or detect_language(pairs), assess_complexity(pairs))


class CodeUploadService:
    def __init__(
        self,
        session: AsyncSession,
        storage: FileStorage,
        document_queue: DocumentQueue | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.document_queue = document_queue
        self.tasks = TaskService(session)

    async def create_task_with_code(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        draft: TaskDraft,
        source: Sequence[IncomingFile] | PastedCode,
    ) -> UploadResult:
        """Files and folders come as IncomingFile parts, pasted code as PastedCode.

        Order of failures: project ownership, task fields, then the upload.
        """
        await self.tasks.projects.get_for_user(project_id, user_id)
        draft = clean_draft(draft)
        excluded: list[str] = []
        if isinstance(source, PastedCode):
            files = prepare_pasted_code(source)
            chosen_language = source.language
        else:
            files, excluded = prepare_files(source, draft.upload_method)
            chosen_language = None
        analysis = await asyncio.to_thread(analyze, files, chosen_language)
        task = await self._store(project_id, user_id, draft, files, analysis)
        if self.document_queue is not None:
            # T096: only after the commit, so the worker finds the task. The
            # queue never raises, so a queueing problem cannot fail the upload.
            await self.document_queue.enqueue(task.id)
        return UploadResult(task, excluded)

    async def _store(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        draft: TaskDraft,
        files: list[PreparedFile],
        analysis: Analysis,
    ) -> Task:
        written: list[str] = []
        try:
            task = await self.tasks.add_for_user(project_id, user_id, draft)
            rows = []
            for file in sorted(files, key=lambda f: (f.file_path, f.file_name)):
                stored_path = self.storage.save(
                    user_id, task.id, file.extension, file.text
                )
                written.append(stored_path)
                rows.append(_code_file(file, stored_path))
            self.session.add(_uploaded_code(task, rows, analysis))
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            self.storage.delete(written)
            raise
        return task


def _code_file(file: PreparedFile, stored_path: str) -> CodeFile:
    return CodeFile(
        file_name=file.file_name,
        file_path=file.file_path,
        file_extension=file.extension,
        file_size_bytes=file.size_bytes,
        storage_path=stored_path,
    )


def _uploaded_code(
    task: Task, rows: list[CodeFile], analysis: Analysis
) -> UploadedCode:
    return UploadedCode(
        task=task,
        files=rows,
        detected_language=analysis.language,
        complexity_level=analysis.report.level,
        total_lines=analysis.report.total_lines,
        total_files=len(rows),
        upload_size_bytes=sum(row.file_size_bytes or 0 for row in rows),
    )

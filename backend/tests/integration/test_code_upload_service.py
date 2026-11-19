"""Runs CodeUploadService against PostgreSQL and a temporary folder (T069)."""

import tempfile
import unittest
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.exceptions import AppError, FieldValidationError
from src.db.session import Database
from src.models import CodeFile, Project, Task, UploadedCode, User
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.code_analysis.upload_files import IncomingFile, PastedCode
from src.services.project_service import ProjectForbiddenError, ProjectNotFoundError
from src.services.task_service import TaskDraft
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
)

LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)
FILE_DRAFT = TaskDraft("할 일 추가 기능", "설명", "file")
FOLDER_DRAFT = TaskDraft("폴더 업로드 시험", None, "folder")
PASTE_DRAFT = TaskDraft("붙여넣기 시험", None, "paste")
APP_JS = b"function add(a, b) {\r\n  return a + b;\r\n}\r\n"


def stored_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class CodeUploadServiceTestCase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.storage = FileStorage(self.root)
        self.database = Database(TEST_DATABASE_URL)
        self.user_id = await self._add_user("learner@example.com")
        self.other_id = await self._add_user("other@example.com")
        self.project_id = await self._add_project(self.user_id)

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add_user(self, email: str) -> uuid.UUID:
        async with self.database.session() as session:
            user = User(email=email, password_hash="hash")
            session.add(user)
            await session.commit()
            return user.id

    async def _add_project(self, user_id: uuid.UUID) -> uuid.UUID:
        async with self.database.session() as session:
            project = Project(user_id=user_id, title="App", last_activity_at=LONG_AGO)
            session.add(project)
            await session.commit()
            return project.id

    async def _upload(
        self,
        draft: TaskDraft,
        source: list[IncomingFile] | PastedCode,
        user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> Task:
        async with self.database.session() as session:
            service = CodeUploadService(session, self.storage)
            result = await service.create_task_with_code(
                project_id or self.project_id, user_id or self.user_id, draft, source
            )
            self.excluded = result.excluded_paths
            return result.task

    async def _counts(self) -> tuple[int, int, int]:
        async with self.database.session() as session:
            tasks = await session.scalars(select(Task))
            codes = await session.scalars(select(UploadedCode))
            files = await session.scalars(select(CodeFile))
            return len(tasks.all()), len(codes.all()), len(files.all())

    async def _stored_code(self, task_id: uuid.UUID) -> UploadedCode:
        async with self.database.session() as session:
            code = await session.scalar(
                select(UploadedCode)
                .options(selectinload(UploadedCode.files))
                .where(UploadedCode.task_id == task_id)
            )
        assert code is not None
        return code


class TestFileUpload(CodeUploadServiceTestCase):
    async def test_creates_task_code_and_file_rows(self) -> None:
        task = await self._upload(FILE_DRAFT, [IncomingFile("App.js", APP_JS)])
        self.assertEqual((task.task_number, task.title), (1, "할 일 추가 기능"))
        code = await self._stored_code(task.id)
        self.assertEqual(code.detected_language, "javascript")
        self.assertEqual(code.complexity_level, "beginner")
        self.assertEqual((code.total_files, code.upload_size_bytes), (1, len(APP_JS)))
        self.assertEqual(code.total_lines, 3)
        (file,) = code.files
        self.assertEqual(
            (file.file_name, file.file_path, file.file_extension, file.file_size_bytes),
            ("App.js", "App.js", ".js", len(APP_JS)),
        )

    async def test_result_task_carries_code_and_files_in_path_order(self) -> None:
        task = await self._upload(
            FOLDER_DRAFT,
            [
                IncomingFile("app/b.py", b"x = 1\n"),
                IncomingFile("app/a.py", b"y = 2\n"),
                IncomingFile("app/lib/c.py", b"z = 3\n"),
            ],
        )
        assert task.uploaded_code is not None
        paths = [f.file_path for f in task.uploaded_code.files]
        self.assertEqual(paths, ["app/a.py", "app/b.py", "app/lib/c.py"])
        self.assertEqual(task.uploaded_code.total_files, 3)

    async def test_files_are_stored_as_utf8_lf_under_user_and_task(self) -> None:
        task = await self._upload(FILE_DRAFT, [IncomingFile("App.js", APP_JS)])
        code = await self._stored_code(task.id)
        (file,) = code.files
        path = self.root / file.storage_path
        self.assertEqual(path.parent, self.root / str(self.user_id) / str(task.id))
        self.assertNotIn("App", path.name)
        self.assertEqual(
            path.read_bytes(), b"function add(a, b) {\n  return a + b;\n}\n"
        )
        self.assertEqual(self.storage.read(file.storage_path)[:8], "function")

    async def test_reads_cp949_and_bom_files(self) -> None:
        task = await self._upload(
            FOLDER_DRAFT,
            [
                IncomingFile("a.txt", "# 한글 주석\n".encode("cp949")),
                IncomingFile("b.txt", b"\xef\xbb\xbfhello\n"),
            ],
        )
        code = await self._stored_code(task.id)
        texts = {f.file_name: self.storage.read(f.storage_path) for f in code.files}
        self.assertEqual(texts, {"a.txt": "# 한글 주석\n", "b.txt": "hello\n"})

    async def test_picks_the_main_language_of_a_folder(self) -> None:
        task = await self._upload(
            FOLDER_DRAFT,
            [
                IncomingFile("app/main.py", b"a = 1\nb = 2\nc = 3\n"),
                IncomingFile("app/page.html", b"<p>hi</p>\n"),
                IncomingFile("README.md", b"# readme\n"),
            ],
        )
        self.assertEqual((await self._stored_code(task.id)).detected_language, "python")

    async def test_excluded_paths_are_dropped_and_reported(self) -> None:
        task = await self._upload(
            FOLDER_DRAFT,
            [
                IncomingFile("app/main.py", b"a = 1\n"),
                IncomingFile("app/node_modules/x/index.js", b"x\n"),
                IncomingFile("app/.git/config", b"x\n"),
            ],
        )
        self.assertEqual(
            self.excluded, ["app/node_modules/x/index.js", "app/.git/config"]
        )
        code = await self._stored_code(task.id)
        self.assertEqual([f.file_path for f in code.files], ["app/main.py"])
        self.assertEqual(len(stored_files(self.root)), 1)

    async def test_updates_the_project_last_activity(self) -> None:
        await self._upload(FILE_DRAFT, [IncomingFile("a.py", b"x = 1\n")])
        async with self.database.session() as session:
            project = await session.get(Project, self.project_id)
        assert project is not None
        self.assertGreater(project.last_activity_at, LONG_AGO)

    async def test_task_numbers_continue_per_project(self) -> None:
        first = await self._upload(FILE_DRAFT, [IncomingFile("a.py", b"x = 1\n")])
        second = await self._upload(FILE_DRAFT, [IncomingFile("a.py", b"x = 1\n")])
        self.assertEqual((first.task_number, second.task_number), (1, 2))


class TestPasteUpload(CodeUploadServiceTestCase):
    async def test_stores_pasted_code_with_the_chosen_language(self) -> None:
        task = await self._upload(
            PASTE_DRAFT, PastedCode("def add(a, b):\r\n    return a + b\r\n", "python")
        )
        code = await self._stored_code(task.id)
        self.assertEqual(task.upload_method, "paste")
        self.assertEqual(code.detected_language, "python")
        (file,) = code.files
        self.assertEqual(
            (file.file_name, file.file_path, file.file_extension),
            ("pasted.py", "pasted.py", ".py"),
        )
        self.assertEqual(
            self.storage.read(file.storage_path), "def add(a, b):\n    return a + b\n"
        )

    async def test_chosen_language_wins_over_detection(self) -> None:
        task = await self._upload(PASTE_DRAFT, PastedCode("print('x')\n", "text"))
        code = await self._stored_code(task.id)
        self.assertEqual(code.detected_language, "text")
        self.assertEqual(code.files[0].file_name, "pasted.txt")

    async def test_blank_code_and_missing_language_are_field_errors(self) -> None:
        for source, field in (
            (PastedCode("  ", "python"), "code"),
            (PastedCode("x = 1", None), "language"),
        ):
            with (
                self.subTest(field=field),
                self.assertRaises(FieldValidationError) as caught,
            ):
                await self._upload(PASTE_DRAFT, source)
            assert caught.exception.details is not None
            self.assertEqual(caught.exception.details["fields"][0]["field"], field)
        self.assertEqual(await self._counts(), (0, 0, 0))


class TestChecksAndRollback(CodeUploadServiceTestCase):
    async def assert_nothing_saved(self) -> None:
        self.assertEqual(await self._counts(), (0, 0, 0))
        self.assertEqual(stored_files(self.root), [])

    async def test_a_rejected_file_saves_nothing(self) -> None:
        cases = {
            "unsupported_file_type": IncomingFile("a.exe", b"x"),
            "binary_file": IncomingFile("a.py", b"\x00\x01"),
            "unsupported_encoding": IncomingFile("a.py", b"ab \xff\xfe"),
            "invalid_file_path": IncomingFile("../a.py", b"x = 1\n"),
            "no_files": IncomingFile("node_modules/a.js", b"x"),
        }
        for error, file in cases.items():
            with self.subTest(error=error), self.assertRaises(AppError) as caught:
                await self._upload(FOLDER_DRAFT, [file])
            self.assertEqual(caught.exception.error, error)
        await self.assert_nothing_saved()

    async def test_a_bad_second_file_leaves_no_first_file_behind(self) -> None:
        with self.assertRaises(AppError):
            await self._upload(
                FOLDER_DRAFT,
                [IncomingFile("a.py", b"x = 1\n"), IncomingFile("b.py", b"\x00")],
            )
        await self.assert_nothing_saved()

    async def test_invalid_task_fields_come_before_file_errors(self) -> None:
        with self.assertRaises(FieldValidationError):
            await self._upload(
                TaskDraft("짧음", None, "file"), [IncomingFile("a.exe", b"x")]
            )

    async def test_ownership_comes_before_everything_else(self) -> None:
        bad = [IncomingFile("a.exe", b"x")]
        with self.assertRaises(ProjectForbiddenError):
            await self._upload(FILE_DRAFT, bad, user_id=self.other_id)
        with self.assertRaises(ProjectNotFoundError):
            await self._upload(FILE_DRAFT, bad, project_id=uuid.uuid4())
        await self.assert_nothing_saved()

    async def test_database_failure_deletes_written_files_and_rows(self) -> None:
        files = [IncomingFile("a.py", b"x = 1\n"), IncomingFile("b.py", b"y = 2\n")]
        with (
            patch(
                "sqlalchemy.ext.asyncio.AsyncSession.commit",
                side_effect=RuntimeError("database went away"),
            ),
            self.assertRaises(RuntimeError),
        ):
            await self._upload(FOLDER_DRAFT, files)
        await self.assert_nothing_saved()

    async def test_failure_while_writing_deletes_the_files_already_written(
        self,
    ) -> None:
        files = [IncomingFile("a.py", b"x = 1\n"), IncomingFile("b.py", b"y = 2\n")]
        real_save = FileStorage.save
        calls = []

        def flaky_save(storage: FileStorage, *args: object) -> str:
            calls.append(args)
            if len(calls) == 2:
                raise OSError("disk full")
            return real_save(storage, *args)  # type: ignore[arg-type]

        with (
            patch.object(FileStorage, "save", flaky_save),
            self.assertRaises(OSError),
        ):
            await self._upload(FOLDER_DRAFT, files)
        await self.assert_nothing_saved()

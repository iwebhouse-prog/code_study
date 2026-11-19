"""Checks the CodeFile model against the real migrated table (T063)."""

import unittest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.db.session import Database
from src.models import CodeFile, Project, Task, UploadedCode, User
from tests.integration.db_utils import (
    TEST_DATABASE_URL,
    database_reachable,
    drop_test_database,
    recreate_test_database,
    run_alembic,
    schema_differences,
)

# Nullable in migration 001 but always filled by its default.
STRICTER_IN_MODEL = ("created_at",)


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestCodeFileMatchesMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    def test_model_matches_table(self) -> None:
        self.assertEqual(schema_differences(CodeFile, STRICTER_IN_MODEL), [])


@unittest.skipUnless(database_reachable(), "PostgreSQL is not running on :5432")
class TestCodeFilePersistence(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        recreate_test_database()
        result = run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_database()

    async def asyncSetUp(self) -> None:
        self.database = Database(TEST_DATABASE_URL)
        async with self.database.session() as session:
            user = User(email="learner@example.com", password_hash="hash")
            session.add(user)
            await session.flush()
            project = Project(user_id=user.id, title="Todo 앱")
            session.add(project)
            await session.flush()
            task = Task(project_id=project.id, task_number=1, title="할 일 추가 기능")
            session.add(task)
            await session.flush()
            self.upload = UploadedCode(task_id=task.id, total_files=2)
            session.add(self.upload)
            await session.commit()

    async def asyncTearDown(self) -> None:
        async with self.database.session() as session:
            for user in (await session.scalars(select(User))).all():
                await session.delete(user)
            await session.commit()
        await self.database.dispose()

    async def _add(self, file_name: str = "main.py", **fields: object) -> CodeFile:
        fields.setdefault("file_extension", ".py")
        fields.setdefault("storage_path", f"storage/uploads/u/t/{file_name}")
        async with self.database.session() as session:
            code_file = CodeFile(
                uploaded_code_id=self.upload.id, file_name=file_name, **fields
            )
            session.add(code_file)
            await session.commit()
            return code_file

    async def _files(self) -> list[CodeFile]:
        async with self.database.session() as session:
            upload = await session.scalar(
                select(UploadedCode).options(selectinload(UploadedCode.files))
            )
        assert upload is not None
        return list(upload.files)

    async def test_file_is_stored_and_created_at_is_readable(self) -> None:
        code_file = await self._add(
            "app.js",
            file_path="src/app.js",
            file_extension=".js",
            file_size_bytes=2048,
            mime_type="text/javascript",
        )
        self.assertIsNotNone(code_file.id)
        self.assertIsNotNone(code_file.created_at)
        async with self.database.session() as session:
            stored = await session.get(CodeFile, code_file.id)
        assert stored is not None
        self.assertEqual(
            (stored.file_path, stored.file_extension, stored.file_size_bytes),
            ("src/app.js", ".js", 2048),
        )
        self.assertEqual(stored.mime_type, "text/javascript")

    async def test_every_supported_extension_is_accepted(self) -> None:
        for extension in CodeFile.SUPPORTED_EXTENSIONS:
            await self._add(f"file{extension}", file_extension=extension)
        self.assertEqual(len(await self._files()), len(CodeFile.SUPPORTED_EXTENSIONS))

    async def test_unsupported_extension_is_rejected(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "supported_extension"):
            await self._add("tool.exe", file_extension=".exe")

    async def test_extension_check_is_case_sensitive(self) -> None:
        # The DB only knows lower case; T064 must normalise ".PY" before saving.
        with self.assertRaisesRegex(IntegrityError, "supported_extension"):
            await self._add("MAIN.PY", file_extension=".PY")

    async def test_missing_extension_passes_the_database_check(self) -> None:
        # SQL CHECK lets NULL through, so the upload service must always set it.
        code_file = await self._add("Makefile", file_extension=None)
        self.assertIsNone(code_file.file_extension)

    async def test_storage_path_is_required(self) -> None:
        with self.assertRaisesRegex(IntegrityError, "storage_path"):
            await self._add(storage_path=None)

    async def test_files_are_listed_by_path_then_name(self) -> None:
        await self._add("b.py", file_path="src/b.py")
        await self._add("a.py", file_path="src/a.py")
        await self._add("README.md", file_path="README.md", file_extension=".md")
        names = [f.file_name for f in await self._files()]
        self.assertEqual(names, ["README.md", "a.py", "b.py"])

    async def test_deleting_the_upload_deletes_its_files(self) -> None:
        await self._add("a.py")
        await self._add("b.py")
        async with self.database.session() as session:
            await session.delete(await session.get(UploadedCode, self.upload.id))
            await session.commit()
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(CodeFile))).all(), [])

    async def test_deleting_the_task_deletes_upload_and_files(self) -> None:
        await self._add("a.py")
        async with self.database.session() as session:
            await session.delete(await session.get(Task, self.upload.task_id))
            await session.commit()
        async with self.database.session() as session:
            self.assertEqual((await session.scalars(select(CodeFile))).all(), [])
            self.assertEqual((await session.scalars(select(UploadedCode))).all(), [])

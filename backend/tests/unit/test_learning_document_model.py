"""Verifies the LearningDocument model and its generation states (T090)."""

import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from src.models import LearningDocument, Task
from src.models.base import Base

NOW = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 17, 9, 2, tzinfo=UTC)


def column(name: str):  # type: ignore[no-untyped-def]
    return LearningDocument.__table__.c[name]


def full_content() -> dict[str, object]:
    return {f"chapter{i}": {"title": f"{i}장"} for i in range(1, 8)}


def pending() -> LearningDocument:
    return LearningDocument(
        generation_status="pending", content=LearningDocument.empty_content()
    )


class TestLearningDocumentTable(unittest.TestCase):
    def test_table_name_and_metadata(self) -> None:
        self.assertEqual(LearningDocument.__tablename__, "learning_documents")
        self.assertIs(
            Base.metadata.tables["learning_documents"], LearningDocument.__table__
        )

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(LearningDocument.__table__.c.keys()),
            {
                "id",
                "task_id",
                "content",
                "generation_status",
                "generation_started_at",
                "generation_completed_at",
                "generation_error",
                "celery_task_id",
                "created_at",
                "updated_at",
            },
        )

    def test_task_id_is_unique_and_cascades_from_tasks(self) -> None:
        task_id = column("task_id")
        self.assertFalse(task_id.nullable)
        self.assertTrue(task_id.unique)  # one document per task
        foreign_key = next(iter(task_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "tasks.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_content_is_required_jsonb(self) -> None:
        self.assertIsInstance(column("content").type, JSONB)
        self.assertFalse(column("content").nullable)

    def test_other_columns(self) -> None:
        self.assertEqual(column("generation_status").type.length, 20)
        self.assertIsNotNone(column("generation_status").server_default)
        self.assertIsInstance(column("generation_error").type, Text)
        self.assertIsInstance(column("celery_task_id").type, String)
        self.assertEqual(column("celery_task_id").type.length, 255)
        for name in ("generation_started_at", "generation_completed_at"):
            self.assertTrue(column(name).type.timezone)
            self.assertTrue(column(name).nullable)

    def test_checks_match_migration(self) -> None:
        checks = {
            c.name: str(c.sqltext)
            for c in LearningDocument.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        for status in LearningDocument.STATUSES:
            self.assertIn(
                f"'{status}'", checks["learning_documents_generation_status_check"]
            )
        structure = checks["valid_content_structure"]
        self.assertIn("jsonb_typeof(content) = 'object'", structure)
        for key in LearningDocument.CHAPTER_KEYS:
            self.assertIn(f"content ? '{key}'", structure)

    def test_constants(self) -> None:
        self.assertEqual(
            LearningDocument.STATUSES, ("pending", "in_progress", "completed", "failed")
        )
        self.assertEqual(
            LearningDocument.CHAPTER_KEYS,
            tuple(f"chapter{i}" for i in range(1, 8)),
        )


class TestRelationships(unittest.TestCase):
    def test_document_and_task_point_at_each_other(self) -> None:
        self.assertIs(LearningDocument.task.property.mapper.class_, Task)
        self.assertIs(Task.learning_document.property.mapper.class_, LearningDocument)
        self.assertFalse(Task.learning_document.property.uselist)

    def test_relationships_never_lazy_load(self) -> None:
        self.assertEqual(LearningDocument.task.property.lazy, "raise")
        self.assertEqual(Task.learning_document.property.lazy, "raise")
        self.assertTrue(Task.learning_document.property.passive_deletes)


class TestEmptyContent(unittest.TestCase):
    def test_has_every_chapter_key_and_nothing_else(self) -> None:
        self.assertEqual(
            LearningDocument.empty_content(),
            {key: {} for key in LearningDocument.CHAPTER_KEYS},
        )

    def test_returns_a_fresh_dict_each_time(self) -> None:
        first = LearningDocument.empty_content()
        first["chapter1"]["title"] = "x"
        self.assertEqual(LearningDocument.empty_content()["chapter1"], {})


class TestGenerationStates(unittest.TestCase):
    def test_start_records_the_celery_task_and_time(self) -> None:
        document = pending()
        document.start("celery-1", NOW)
        self.assertEqual(document.generation_status, "in_progress")
        self.assertEqual(document.celery_task_id, "celery-1")
        self.assertEqual(document.generation_started_at, NOW)
        self.assertIsNone(document.generation_completed_at)

    def test_complete_stores_the_content(self) -> None:
        document = pending()
        document.start("celery-1", NOW)
        document.complete(full_content(), LATER)
        self.assertEqual(document.generation_status, "completed")
        self.assertEqual(document.content, full_content())
        self.assertEqual(document.generation_completed_at, LATER)
        self.assertTrue(document.is_completed)

    def test_fail_keeps_the_reason(self) -> None:
        document = pending()
        document.start("celery-1", NOW)
        document.fail("AI 서비스 시간 초과", LATER)
        self.assertEqual(document.generation_status, "failed")
        self.assertEqual(document.generation_error, "AI 서비스 시간 초과")
        self.assertEqual(document.generation_completed_at, LATER)
        self.assertFalse(document.is_completed)

    def test_failed_document_can_be_retried(self) -> None:
        document = pending()
        document.start("celery-1", NOW)
        document.fail("시간 초과", NOW)
        document.start("celery-2", LATER)
        self.assertEqual(document.generation_status, "in_progress")
        self.assertEqual(document.celery_task_id, "celery-2")
        self.assertIsNone(document.generation_error)
        self.assertIsNone(document.generation_completed_at)

    def test_times_default_to_now(self) -> None:
        document = pending()
        before = datetime.now(UTC)
        document.start("celery-1")
        document.complete(full_content())
        assert document.generation_started_at and document.generation_completed_at
        self.assertGreaterEqual(document.generation_started_at, before)
        self.assertGreaterEqual(document.generation_completed_at, before)

    def test_content_missing_a_chapter_is_refused(self) -> None:
        document = pending()
        document.start("celery-1", NOW)
        content = full_content()
        del content["chapter7"]
        with self.assertRaisesRegex(ValueError, "chapter7"):
            document.complete(content, LATER)
        self.assertEqual(document.generation_status, "in_progress")

    def test_only_waiting_or_failed_documents_can_start(self) -> None:
        for status in ("in_progress", "completed"):
            with self.subTest(status=status):
                document = LearningDocument(generation_status=status)
                with self.assertRaisesRegex(ValueError, status):
                    document.start("celery-9", NOW)

    def test_only_running_documents_can_complete_or_fail(self) -> None:
        for status in ("pending", "completed", "failed"):
            with self.subTest(status=status):
                document = LearningDocument(generation_status=status)
                with self.assertRaisesRegex(ValueError, status):
                    document.complete(full_content(), NOW)
                with self.assertRaisesRegex(ValueError, status):
                    document.fail("x", NOW)

    def test_completed_content_cannot_be_replaced(self) -> None:
        # FR-038: a finished document is stored once and never regenerated.
        document = pending()
        document.start("celery-1", NOW)
        document.complete(full_content(), LATER)
        with self.assertRaisesRegex(ValueError, "completed"):
            document.content = LearningDocument.empty_content()
        self.assertEqual(document.content, full_content())


class TestLearningDocumentInstance(unittest.TestCase):
    def test_repr_names_the_task_and_status(self) -> None:
        task_id = uuid.uuid4()
        document = LearningDocument(task_id=task_id, generation_status="pending")
        self.assertIn(str(task_id), repr(document))
        self.assertIn("pending", repr(document))

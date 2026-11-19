"""Verifies LearningDocument.restart(), used by "regenerate" (T095)."""

import unittest
from datetime import UTC, datetime, timedelta

from src.models import LearningDocument

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
FULL = {f"chapter{i}": {"title": f"{i}장"} for i in range(1, 8)}


def document(status: str, started_seconds_ago: int | None = None) -> LearningDocument:
    doc = LearningDocument(
        content=LearningDocument.empty_content(), generation_status=status
    )
    if started_seconds_ago is not None:
        doc.generation_started_at = NOW - timedelta(seconds=started_seconds_ago)
    return doc


class TestStale(unittest.TestCase):
    def test_running_longer_than_300_seconds_is_stale(self) -> None:
        self.assertTrue(document("in_progress", 301).is_stale(NOW))

    def test_running_exactly_300_seconds_is_not_stale_yet(self) -> None:
        self.assertFalse(document("in_progress", 300).is_stale(NOW))

    def test_other_statuses_are_never_stale(self) -> None:
        for status in ("pending", "completed", "failed"):
            with self.subTest(status=status):
                self.assertFalse(document(status, 1000).is_stale(NOW))

    def test_running_without_start_time_is_not_stale(self) -> None:
        self.assertFalse(document("in_progress").is_stale(NOW))

    def test_now_defaults_to_the_current_time(self) -> None:
        self.assertTrue(document("in_progress", 100000).is_stale())


class TestRestart(unittest.TestCase):
    def failed(self) -> LearningDocument:
        doc = document("in_progress", 30)
        doc.celery_task_id = "old"
        doc.fail("ai_unavailable: boom", NOW)
        return doc

    def test_failed_document_goes_back_to_pending_and_is_cleared(self) -> None:
        doc = self.failed()
        self.assertTrue(doc.can_restart(NOW))
        doc.restart(NOW)
        self.assertEqual(doc.generation_status, "pending")
        self.assertIsNone(doc.generation_error)
        self.assertIsNone(doc.generation_started_at)
        self.assertIsNone(doc.generation_completed_at)
        self.assertIsNone(doc.celery_task_id)

    def test_stale_running_document_can_restart(self) -> None:
        doc = document("in_progress", 301)
        doc.celery_task_id = "old"
        self.assertTrue(doc.can_restart(NOW))
        doc.restart(NOW)
        self.assertEqual(doc.generation_status, "pending")
        self.assertIsNone(doc.celery_task_id)
        self.assertIsNone(doc.generation_started_at)

    def test_pending_running_and_completed_documents_are_refused(self) -> None:
        completed = document("in_progress", 10)
        completed.complete(FULL, NOW)
        cases = [document("pending"), document("in_progress", 10), completed]
        for doc in cases:
            with self.subTest(status=doc.generation_status):
                status = doc.generation_status
                self.assertFalse(doc.can_restart(NOW))
                with self.assertRaisesRegex(ValueError, "cannot restart"):
                    doc.restart(NOW)
                self.assertEqual(doc.generation_status, status)

    def test_completed_content_is_untouched_by_a_refused_restart(self) -> None:
        doc = document("in_progress", 10)
        doc.complete(FULL, NOW)
        with self.assertRaises(ValueError):
            doc.restart(NOW)
        self.assertEqual(doc.content, FULL)

    def test_restarted_document_can_start_again(self) -> None:
        doc = self.failed()
        doc.restart(NOW)
        doc.start("new", NOW)
        self.assertEqual(doc.generation_status, "in_progress")

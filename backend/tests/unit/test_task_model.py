"""Verifies the Task model definition, numbering helpers and trash fields (T061)."""

import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql

from src.models import Project, Task
from src.models.base import TRASH_RETENTION, Base


def column(name: str):  # type: ignore[no-untyped-def]
    return Task.__table__.c[name]


class TestTaskTable(unittest.TestCase):
    def test_table_name_and_metadata(self) -> None:
        self.assertEqual(Task.__tablename__, "tasks")
        self.assertIs(Base.metadata.tables["tasks"], Task.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(Task.__table__.c.keys()),
            {
                "id",
                "project_id",
                "task_number",
                "title",
                "description",
                "upload_method",
                "created_at",
                "updated_at",
                "deletion_status",
                "trashed_at",
                "scheduled_deletion_at",
            },
        )

    def test_project_id_cascades_from_projects(self) -> None:
        project_id = column("project_id")
        self.assertFalse(project_id.nullable)
        foreign_key = next(iter(project_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "projects.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_task_number_is_a_required_integer(self) -> None:
        self.assertIsInstance(column("task_number").type, Integer)
        self.assertFalse(column("task_number").nullable)

    def test_title_is_required_text_up_to_255(self) -> None:
        title = column("title")
        self.assertIsInstance(title.type, String)
        self.assertEqual(title.type.length, 255)
        self.assertFalse(title.nullable)

    def test_description_is_optional_text(self) -> None:
        self.assertIsInstance(column("description").type, Text)
        self.assertTrue(column("description").nullable)

    def test_upload_method_is_optional_short_text(self) -> None:
        upload_method = column("upload_method")
        self.assertEqual(upload_method.type.length, 20)
        self.assertTrue(upload_method.nullable)

    def test_checks_match_migration(self) -> None:
        checks = {
            c.name: str(c.sqltext)
            for c in Task.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        # FR-008 / FR-009: title at least 5 characters, description at most 500.
        self.assertIn("char_length(title) >= 5", checks["title_min_length"])
        self.assertIn(
            "char_length(description) <= 500", checks["description_max_length"]
        )
        for method in ("'file'", "'folder'", "'paste'"):
            self.assertIn(method, checks["tasks_upload_method_check"])
        self.assertIn("'trashed'", checks["tasks_deletion_status_check"])

    def test_task_number_is_unique_within_a_project(self) -> None:
        uniques = {
            c.name: [col.name for col in c.columns]
            for c in Task.__table__.constraints
            if isinstance(c, UniqueConstraint)
        }
        self.assertEqual(
            uniques["unique_task_number_per_project"], ["project_id", "task_number"]
        )

    def test_upload_methods_constant(self) -> None:
        self.assertEqual(Task.UPLOAD_METHODS, ("file", "folder", "paste"))


class TestRelationships(unittest.TestCase):
    def test_task_and_project_point_at_each_other(self) -> None:
        self.assertIs(Task.project.property.mapper.class_, Project)
        self.assertIs(Project.tasks.property.mapper.class_, Task)

    def test_relationships_never_lazy_load(self) -> None:
        self.assertEqual(Task.project.property.lazy, "raise")
        self.assertEqual(Project.tasks.property.lazy, "raise")
        self.assertTrue(Project.tasks.property.passive_deletes)

    def test_project_lists_tasks_in_number_order(self) -> None:
        # FR-003: tasks are shown in task-number order.
        order_by = Project.tasks.property.order_by
        self.assertEqual([c.name for c in order_by], ["task_number"])


class TestTaskNumbering(unittest.TestCase):
    def test_next_number_query_is_max_plus_one_for_the_project(self) -> None:
        project_id = uuid.uuid4()
        sql = str(
            Task.next_number_query(project_id).compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        self.assertIn("coalesce(max(tasks.task_number), 0) + 1", sql)
        self.assertIn(f"tasks.project_id = '{project_id}'", sql)
        # Trashed tasks keep their numbers, so they are counted too (FR-004).
        self.assertNotIn("deletion_status", sql)

    def test_number_can_be_set_once(self) -> None:
        task = Task(task_number=1)
        self.assertEqual(task.task_number, 1)

    def test_setting_the_same_number_again_is_allowed(self) -> None:
        task = Task(task_number=2)
        task.task_number = 2
        self.assertEqual(task.task_number, 2)

    def test_number_cannot_change_once_assigned(self) -> None:
        # FR-004/FR-005: task numbers are immutable; tasks cannot be reordered.
        task = Task(task_number=1)
        with self.assertRaisesRegex(ValueError, "task_number"):
            task.task_number = 3
        self.assertEqual(task.task_number, 1)


class TestTrash(unittest.TestCase):
    def test_new_task_is_not_trashed(self) -> None:
        self.assertFalse(Task(deletion_status="active").is_trashed)

    def test_move_to_trash_and_restore(self) -> None:
        task = Task(deletion_status="active")
        now = datetime(2026, 11, 12, tzinfo=UTC)
        task.move_to_trash(now)
        self.assertTrue(task.is_trashed)
        self.assertEqual(task.scheduled_deletion_at, now + TRASH_RETENTION)
        task.restore()
        self.assertFalse(task.is_trashed)
        self.assertIsNone(task.trashed_at)


class TestTaskInstance(unittest.TestCase):
    def test_repr_names_the_number_and_title(self) -> None:
        task = Task(id=uuid.uuid4(), task_number=3, title="로그인 기능 만들기")
        self.assertIn("3", repr(task))
        self.assertIn("로그인 기능 만들기", repr(task))

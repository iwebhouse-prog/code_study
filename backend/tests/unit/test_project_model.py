"""Verifies the Project model definition and its trash fields (T043)."""

import unittest
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import CheckConstraint, String, Text

from src.models import Project, User
from src.models.base import TRASH_RETENTION, Base


def column(name: str):  # type: ignore[no-untyped-def]
    return Project.__table__.c[name]


class TestProjectTable(unittest.TestCase):
    def test_table_name_and_metadata(self) -> None:
        self.assertEqual(Project.__tablename__, "projects")
        self.assertIs(Base.metadata.tables["projects"], Project.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(Project.__table__.c.keys()),
            {
                "id",
                "user_id",
                "title",
                "description",
                "created_at",
                "updated_at",
                "last_activity_at",
                "deletion_status",
                "trashed_at",
                "scheduled_deletion_at",
            },
        )

    def test_user_id_cascades_from_users(self) -> None:
        user_id = column("user_id")
        self.assertFalse(user_id.nullable)
        foreign_key = next(iter(user_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "users.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_title_is_required_text_up_to_255(self) -> None:
        title = column("title")
        self.assertIsInstance(title.type, String)
        self.assertEqual(title.type.length, 255)
        self.assertFalse(title.nullable)

    def test_description_is_optional_text(self) -> None:
        self.assertIsInstance(column("description").type, Text)
        self.assertTrue(column("description").nullable)

    def test_last_activity_defaults_to_now(self) -> None:
        last_activity_at = column("last_activity_at")
        self.assertTrue(last_activity_at.type.timezone)
        self.assertIsNotNone(last_activity_at.server_default)

    def test_checks_match_migration(self) -> None:
        checks = {
            c.name: str(c.sqltext)
            for c in Project.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        self.assertIn("char_length(title) >= 1", checks["title_min_length"])
        self.assertIn("'trashed'", checks["projects_deletion_status_check"])


class TestRelationships(unittest.TestCase):
    def test_project_and_user_point_at_each_other(self) -> None:
        self.assertIs(Project.user.property.mapper.class_, User)
        self.assertIs(User.projects.property.mapper.class_, Project)

    def test_relationships_never_lazy_load(self) -> None:
        self.assertEqual(Project.user.property.lazy, "raise")
        self.assertEqual(User.projects.property.lazy, "raise")
        self.assertTrue(User.projects.property.passive_deletes)


class TestTrash(unittest.TestCase):
    def test_retention_is_thirty_days(self) -> None:
        # spec.md FR-009F/H: restorable for 30 days, then deleted for good.
        self.assertEqual(TRASH_RETENTION, timedelta(days=30))

    def test_new_project_is_not_trashed(self) -> None:
        self.assertFalse(Project(deletion_status="active").is_trashed)

    def test_move_to_trash_sets_all_three_fields(self) -> None:
        project = Project(deletion_status="active")
        now = datetime(2026, 11, 9, tzinfo=UTC)
        project.move_to_trash(now)
        self.assertEqual(project.deletion_status, "trashed")
        self.assertEqual(project.trashed_at, now)
        self.assertEqual(project.scheduled_deletion_at, now + TRASH_RETENTION)
        self.assertTrue(project.is_trashed)

    def test_move_to_trash_uses_the_current_time_by_default(self) -> None:
        project = Project(deletion_status="active")
        before = datetime.now(UTC)
        project.move_to_trash()
        assert project.trashed_at is not None
        self.assertGreaterEqual(project.trashed_at, before)

    def test_restore_clears_all_three_fields(self) -> None:
        project = Project(deletion_status="active")
        project.move_to_trash()
        project.restore()
        self.assertEqual(project.deletion_status, "active")
        self.assertIsNone(project.trashed_at)
        self.assertIsNone(project.scheduled_deletion_at)
        self.assertFalse(project.is_trashed)


class TestProjectInstance(unittest.TestCase):
    def test_repr_names_the_project(self) -> None:
        project = Project(id=uuid.uuid4(), title="Python 기초")
        self.assertIn("Python 기초", repr(project))

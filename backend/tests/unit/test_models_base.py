"""Verifies the shared SQLAlchemy base class and column mixins (T009)."""

import unittest
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class _MixinSample(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "_mixin_sample"

    name: Mapped[str] = mapped_column(String(50))
    seen_at: Mapped[datetime | None]


def column(name: str):  # type: ignore[no-untyped-def]
    return _MixinSample.__table__.c[name]


class TestBase(unittest.TestCase):
    def test_base_is_declarative(self) -> None:
        self.assertTrue(issubclass(Base, DeclarativeBase))

    def test_datetime_annotations_map_to_timezone_aware_timestamps(self) -> None:
        seen_at = column("seen_at")
        self.assertIsInstance(seen_at.type, DateTime)
        self.assertTrue(seen_at.type.timezone)
        self.assertTrue(seen_at.nullable)


class TestUUIDPrimaryKeyMixin(unittest.TestCase):
    def test_id_is_uuid_primary_key_generated_by_database(self) -> None:
        id_column = column("id")
        self.assertTrue(id_column.primary_key)
        self.assertIsInstance(id_column.type, Uuid)
        self.assertIn("gen_random_uuid", str(id_column.server_default.arg))

    def test_id_python_type_is_uuid(self) -> None:
        self.assertIs(column("id").type.python_type, uuid.UUID)


class TestTimestampMixin(unittest.TestCase):
    def test_created_at_defaults_to_now(self) -> None:
        created_at = column("created_at")
        self.assertTrue(created_at.type.timezone)
        self.assertIsNotNone(created_at.server_default)
        self.assertIsNone(created_at.onupdate)

    def test_database_set_values_come_back_with_each_write(self) -> None:
        self.assertIs(inspect(_MixinSample).eager_defaults, True)

    def test_updated_at_refreshes_on_update(self) -> None:
        updated_at = column("updated_at")
        self.assertTrue(updated_at.type.timezone)
        self.assertIsNotNone(updated_at.server_default)
        self.assertIsNotNone(updated_at.onupdate)


class TestSoftDeleteMixin(unittest.TestCase):
    def test_deletion_status_defaults_to_active(self) -> None:
        status = column("deletion_status")
        self.assertEqual(status.type.length, 20)
        self.assertIn("active", str(status.server_default.arg))
        self.assertFalse(status.nullable)

    def test_trash_timestamps_are_optional(self) -> None:
        for name in ("trashed_at", "scheduled_deletion_at"):
            self.assertTrue(column(name).nullable)
            self.assertTrue(column(name).type.timezone)


if __name__ == "__main__":
    unittest.main()

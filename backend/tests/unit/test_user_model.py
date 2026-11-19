"""Verifies the User model definition (T023)."""

import unittest
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Uuid

from src.models.base import Base
from src.models.user import User


def column(name: str):  # type: ignore[no-untyped-def]
    return User.__table__.c[name]


class TestUserTable(unittest.TestCase):
    def test_table_name(self) -> None:
        self.assertEqual(User.__tablename__, "users")

    def test_is_registered_on_shared_metadata(self) -> None:
        self.assertIs(Base.metadata.tables["users"], User.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(User.__table__.c.keys()),
            {
                "id",
                "email",
                "password_hash",
                "skill_level",
                "created_at",
                "updated_at",
                "last_login_at",
            },
        )

    def test_id_is_database_generated_uuid(self) -> None:
        self.assertIsInstance(column("id").type, Uuid)
        self.assertIn("gen_random_uuid", str(column("id").server_default.arg))

    def test_email_is_required_and_unique(self) -> None:
        email = column("email")
        self.assertIsInstance(email.type, String)
        self.assertEqual(email.type.length, 255)
        self.assertFalse(email.nullable)
        self.assertTrue(email.unique)

    def test_password_hash_is_required(self) -> None:
        password_hash = column("password_hash")
        self.assertEqual(password_hash.type.length, 255)
        self.assertFalse(password_hash.nullable)

    def test_skill_level_defaults_to_complete_beginner(self) -> None:
        skill_level = column("skill_level")
        self.assertEqual(skill_level.type.length, 50)
        self.assertIn("Complete Beginner", str(skill_level.server_default.arg))

    def test_last_login_at_is_optional_and_timezone_aware(self) -> None:
        last_login_at = column("last_login_at")
        self.assertIsInstance(last_login_at.type, DateTime)
        self.assertTrue(last_login_at.type.timezone)
        self.assertTrue(last_login_at.nullable)

    def test_email_format_check_matches_migration(self) -> None:
        checks = [
            c for c in User.__table__.constraints if isinstance(c, CheckConstraint)
        ]
        self.assertEqual([c.name for c in checks], ["valid_email"])
        self.assertIn("~*", str(checks[0].sqltext))


class TestUserInstance(unittest.TestCase):
    def test_repr_never_shows_the_password_hash(self) -> None:
        # data-model.md: never log password_hash.
        user = User(
            id=uuid.uuid4(), email="a@example.com", password_hash="$2b$12$secret"
        )
        self.assertNotIn("secret", repr(user))
        self.assertIn("a@example.com", repr(user))

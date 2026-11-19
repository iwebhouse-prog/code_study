"""Verifies the RefreshToken model definition (T024)."""

import unittest
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Uuid

from src.models.base import Base
from src.models.refresh_token import RefreshToken
from src.models.user import User


def column(name: str):  # type: ignore[no-untyped-def]
    return RefreshToken.__table__.c[name]


class TestRefreshTokenTable(unittest.TestCase):
    def test_table_name(self) -> None:
        self.assertEqual(RefreshToken.__tablename__, "refresh_tokens")

    def test_is_registered_on_shared_metadata(self) -> None:
        self.assertIs(Base.metadata.tables["refresh_tokens"], RefreshToken.__table__)

    def test_columns_match_data_model(self) -> None:
        self.assertEqual(
            set(RefreshToken.__table__.c.keys()),
            {
                "id",
                "user_id",
                "token_hash",
                "expires_at",
                "created_at",
                "revoked",
                "revoked_at",
            },
        )

    def test_id_is_database_generated_uuid(self) -> None:
        self.assertIsInstance(column("id").type, Uuid)
        self.assertIn("gen_random_uuid", str(column("id").server_default.arg))

    def test_user_id_cascades_from_users(self) -> None:
        user_id = column("user_id")
        self.assertFalse(user_id.nullable)
        foreign_key = next(iter(user_id.foreign_keys))
        self.assertEqual(foreign_key.target_fullname, "users.id")
        self.assertEqual(foreign_key.ondelete, "CASCADE")

    def test_token_hash_is_required_and_unique(self) -> None:
        token_hash = column("token_hash")
        self.assertIsInstance(token_hash.type, String)
        self.assertEqual(token_hash.type.length, 255)
        self.assertFalse(token_hash.nullable)
        self.assertTrue(token_hash.unique)

    def test_expires_at_is_required_and_timezone_aware(self) -> None:
        expires_at = column("expires_at")
        self.assertIsInstance(expires_at.type, DateTime)
        self.assertTrue(expires_at.type.timezone)
        self.assertFalse(expires_at.nullable)

    def test_created_at_defaults_to_now(self) -> None:
        self.assertTrue(column("created_at").type.timezone)
        self.assertIsNotNone(column("created_at").server_default)

    def test_revoked_defaults_to_false(self) -> None:
        revoked = column("revoked")
        self.assertIsInstance(revoked.type, Boolean)
        self.assertIn("false", str(revoked.server_default.arg).lower())

    def test_revoked_at_is_optional(self) -> None:
        self.assertTrue(column("revoked_at").nullable)


class TestRelationships(unittest.TestCase):
    def test_token_and_user_point_at_each_other(self) -> None:
        self.assertIs(RefreshToken.user.property.mapper.class_, User)
        self.assertIs(User.refresh_tokens.property.mapper.class_, RefreshToken)

    def test_relationships_never_lazy_load(self) -> None:
        # Async sessions cannot lazy-load; "raise" gives a clear error instead.
        self.assertEqual(RefreshToken.user.property.lazy, "raise")
        self.assertEqual(User.refresh_tokens.property.lazy, "raise")

    def test_deleting_a_user_leaves_token_cleanup_to_the_database(self) -> None:
        self.assertTrue(User.refresh_tokens.property.passive_deletes)


class TestRefreshTokenInstance(unittest.TestCase):
    def test_repr_never_shows_the_token_hash(self) -> None:
        token = RefreshToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash="abc123secret",
            expires_at=datetime.now(UTC),
        )
        self.assertNotIn("abc123secret", repr(token))

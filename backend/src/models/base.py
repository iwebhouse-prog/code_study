import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, String, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        uuid.UUID: Uuid,
    }


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampMixin:
    # Fetch database-set values with each INSERT/UPDATE: async sessions cannot
    # lazy-load, so reading updated_at afterwards would raise MissingGreenlet.
    __mapper_args__ = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


# spec.md FR-009F/H: trashed items can be restored for 30 days, then they are
# deleted for good.
TRASH_RETENTION = timedelta(days=30)


class SoftDeleteMixin:
    deletion_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'active'")
    )
    trashed_at: Mapped[datetime | None]
    scheduled_deletion_at: Mapped[datetime | None]

    @property
    def is_trashed(self) -> bool:
        return self.deletion_status == "trashed"

    # The only places that change the three trash fields, so they stay in step.
    def move_to_trash(self, now: datetime | None = None) -> None:
        trashed_at = now or datetime.now(UTC)
        self.deletion_status = "trashed"
        self.trashed_at = trashed_at
        self.scheduled_deletion_at = trashed_at + TRASH_RETENTION

    def restore(self) -> None:
        self.deletion_status = "active"
        self.trashed_at = None
        self.scheduled_deletion_at = None

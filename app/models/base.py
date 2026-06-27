"""
Shared mixins injected into every model table.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID


class UUIDMixin:
    """UUID primary key."""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)


class TimestampMixin:
    """Auto-managed created_at / updated_at."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    """Soft-delete via deleted_at nullable timestamp."""
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()


class BaseModelMixin(UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Full mixin: UUID PK + timestamps + soft delete."""
    pass

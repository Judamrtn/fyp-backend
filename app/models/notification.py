import enum
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class NotificationType(str, enum.Enum):
    PROPOSAL_SUBMITTED         = "proposal_submitted"
    PROPOSAL_APPROVED          = "proposal_approved"
    PROPOSAL_REJECTED          = "proposal_rejected"
    REVISION_REQUESTED         = "revision_requested"
    COMMENT_ADDED              = "comment_added"
    SUPERVISOR_ASSIGNED        = "supervisor_assigned"
    SUPERVISOR_FIRST_APPROVAL  = "supervisor_first_approval"
    DEADLINE_REMINDER          = "deadline_reminder"
    GENERAL                    = "general"


class Notification(Base, BaseModelMixin):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type    = Column(Enum(NotificationType), nullable=False, default=NotificationType.GENERAL)
    title   = Column(String(255), nullable=False)
    body    = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    link    = Column(String(500), nullable=True)

    user = relationship("User", back_populates="notifications")


class ActivityLog(Base, BaseModelMixin):
    """
    Immutable audit trail for admin visibility.
    entity_type: "proposal" | "user" | "department" | ...
    """
    __tablename__ = "activity_logs"

    actor_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action      = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id   = Column(UUID(as_uuid=True), nullable=True)
    extra_data  = Column(JSONB, nullable=True)   # 'metadata' is reserved by SQLAlchemy
    ip_address  = Column(String(50), nullable=True)

    actor = relationship("User", back_populates="activity_logs")
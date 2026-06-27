"""
Phase 2 — Project Supervision models.
"""
import enum
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Enum, Date, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class ProgressStatus(str, enum.Enum):
    SUBMITTED      = "submitted"
    UNDER_REVIEW   = "under_review"
    APPROVED       = "approved"
    NEEDS_REVISION = "needs_revision"


class DocumentType(str, enum.Enum):
    UPLOAD     = "upload"
    GOOGLE_DOC = "google_doc"


class RecommendationStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProjectMilestone(Base, BaseModelMixin):
    """Flexible milestones created by supervisor."""
    __tablename__ = "project_milestones"

    proposal_id  = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id"),     nullable=False)
    title        = Column(String(300), nullable=False)
    description  = Column(Text, nullable=True)
    due_date     = Column(Date, nullable=True)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(String(50), nullable=True)

    proposal = relationship("Proposal",       back_populates="milestones")
    creator  = relationship("User",           foreign_keys=[created_by])
    progress = relationship("ProjectProgress", back_populates="milestone")


class ProjectProgress(Base, BaseModelMixin):
    """Progress update submitted by student — file upload or Google Doc link."""
    __tablename__ = "project_progress"

    proposal_id   = Column(UUID(as_uuid=True), ForeignKey("proposals.id"),          nullable=False, index=True)
    milestone_id  = Column(UUID(as_uuid=True), ForeignKey("project_milestones.id"), nullable=True)
    submitted_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"),              nullable=False)
    title         = Column(String(300), nullable=False)
    description   = Column(Text, nullable=True)
    document_url  = Column(String(1000), nullable=True)
    document_type = Column(Enum(DocumentType), nullable=True)
    status        = Column(Enum(ProgressStatus), default=ProgressStatus.SUBMITTED, nullable=False)

    proposal  = relationship("Proposal",         back_populates="progress_updates")
    milestone = relationship("ProjectMilestone",  back_populates="progress")
    student   = relationship("User",             foreign_keys=[submitted_by])
    feedback  = relationship("ProgressFeedback", back_populates="progress",
                             order_by="ProgressFeedback.created_at")


class ProgressFeedback(Base, BaseModelMixin):
    """
    Feedback given by supervisor on a progress update.
    Student can reply to feedback via threaded replies.
    """
    __tablename__ = "progress_feedback"

    progress_id   = Column(UUID(as_uuid=True), ForeignKey("project_progress.id"), nullable=False, index=True)
    supervisor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"),            nullable=False)
    feedback_text = Column(Text, nullable=False)
    status_update = Column(Enum(ProgressStatus), nullable=False)

    # Threaded replies — student or supervisor can reply
    replies = relationship("FeedbackReply", back_populates="feedback",
                           order_by="FeedbackReply.created_at")

    progress   = relationship("ProjectProgress", back_populates="feedback")
    supervisor = relationship("User",            foreign_keys=[supervisor_id])


class FeedbackReply(Base, BaseModelMixin):
    """
    Reply to a progress feedback — used by student to respond to supervisor feedback.
    """
    __tablename__ = "feedback_replies"

    feedback_id = Column(UUID(as_uuid=True), ForeignKey("progress_feedback.id"), nullable=False, index=True)
    sender_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"),             nullable=False)
    message     = Column(Text, nullable=False)

    feedback = relationship("ProgressFeedback", back_populates="replies")
    sender   = relationship("User",             foreign_keys=[sender_id])


class SupervisionMessage(Base, BaseModelMixin):
    """
    General chat between student and supervisor during supervision phase.
    Available only when proposal status = UNDER_SUPERVISION.
    """
    __tablename__ = "supervision_messages"

    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    sender_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"),     nullable=False)
    message     = Column(Text, nullable=False)
    is_read     = Column(Boolean, default=False)

    proposal = relationship("Proposal", back_populates="supervision_messages")
    sender   = relationship("User",     foreign_keys=[sender_id])


class DefenceRecommendation(Base, BaseModelMixin):
    """Supervisor recommends student for final defence. HOD approves or rejects."""
    __tablename__ = "defence_recommendations"

    proposal_id         = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, unique=True)
    supervisor_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"),     nullable=False)
    recommendation_note = Column(Text, nullable=False)
    status              = Column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING)
    hod_note            = Column(Text, nullable=True)
    reviewed_by         = Column(UUID(as_uuid=True), ForeignKey("users.id"),     nullable=True)

    proposal   = relationship("Proposal", back_populates="defence_recommendation")
    supervisor = relationship("User",     foreign_keys=[supervisor_id])
    reviewer   = relationship("User",     foreign_keys=[reviewed_by])
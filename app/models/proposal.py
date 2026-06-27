import enum
from sqlalchemy import (
    Column, String, Text, Enum, Float, Boolean,
    Integer, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class ProposalStatus(str, enum.Enum):
    DRAFT               = "draft"
    PENDING             = "pending"
    UNDER_REVIEW        = "under_review"
    REVISION_REQUIRED   = "revision_required"
    SUPERVISOR_APPROVED = "supervisor_approved"
    APPROVED            = "approved"
    REJECTED            = "rejected"
    WITHDRAWN           = "withdrawn"
    UNDER_SUPERVISION   = "under_supervision"   # Phase 2: active project


class Proposal(Base, BaseModelMixin):
    __tablename__ = "proposals"

    student_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"),          nullable=False, index=True)
    supervisor_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),          nullable=True)
    department_id    = Column(UUID(as_uuid=True), ForeignKey("departments.id"),    nullable=False, index=True)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)

    title            = Column(String(500), nullable=False)
    abstract         = Column(Text, nullable=True)
    keywords         = Column(Text, nullable=True)

    status           = Column(Enum(ProposalStatus), default=ProposalStatus.DRAFT, nullable=False, index=True)
    submission_date  = Column(String(50), nullable=True)
    approval_date    = Column(String(50), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    similarity_score = Column(Float,   nullable=True)
    similarity_flag  = Column(Boolean, default=False)

    # Relationships
    student      = relationship("User", foreign_keys=[student_id], back_populates="proposals")
    supervisor   = relationship("User", foreign_keys=[supervisor_id])
    department   = relationship("Department",    back_populates="proposals")
    academic_year = relationship("AcademicYear", back_populates="proposals")

    objectives        = relationship("ProposalObjective",  back_populates="proposal",
                                     order_by="ProposalObjective.order_number")
    versions          = relationship("ProposalVersion",    back_populates="proposal",
                                     order_by="ProposalVersion.version_number")
    documents         = relationship("ProposalDocument",   back_populates="proposal")
    comments          = relationship("ProposalComment",    back_populates="proposal",
                                     order_by="ProposalComment.created_at")
    status_logs       = relationship("ProposalStatusLog",  back_populates="proposal",
                                     order_by="ProposalStatusLog.created_at")
    similarity_checks = relationship("SimilarityCheck",    back_populates="proposal")
    allocation        = relationship("SupervisorAllocation", back_populates="proposal", uselist=False)
    registration      = relationship("ProjectRegistration",  back_populates="proposal",
                                     foreign_keys="ProjectRegistration.proposal_id", uselist=False)

    # Phase 2
    milestones           = relationship("ProjectMilestone",      back_populates="proposal",
                                        order_by="ProjectMilestone.created_at")
    progress_updates     = relationship("ProjectProgress",       back_populates="proposal",
                                        order_by="ProjectProgress.created_at")
    defence_recommendation = relationship("DefenceRecommendation", back_populates="proposal", uselist=False)
    supervision_messages   = relationship("SupervisionMessage",   back_populates="proposal",
                                          order_by="SupervisionMessage.created_at")


class ProposalObjective(Base, BaseModelMixin):
    __tablename__ = "proposal_objectives"

    proposal_id    = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    objective_text = Column(Text, nullable=False)
    order_number   = Column(Integer, nullable=False, default=1)

    proposal = relationship("Proposal", back_populates="objectives")


class ProposalVersion(Base, BaseModelMixin):
    __tablename__ = "proposal_versions"

    proposal_id    = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    title          = Column(String(500), nullable=False)
    abstract       = Column(Text, nullable=True)
    keywords       = Column(Text, nullable=True)
    objectives     = Column(Text, nullable=True)
    snapshot_at    = Column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("proposal_id", "version_number"),)

    proposal = relationship("Proposal", back_populates="versions")


class ProposalDocument(Base, BaseModelMixin):
    __tablename__ = "proposal_documents"

    proposal_id  = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    file_name    = Column(String(255), nullable=False)
    file_type    = Column(String(100), nullable=False)
    file_size    = Column(Integer,     nullable=False)
    storage_key  = Column(String(500), nullable=False)
    version_no   = Column(Integer, default=1, nullable=False)
    is_active    = Column(Boolean, default=True)

    proposal = relationship("Proposal", back_populates="documents")


class ProposalComment(Base, BaseModelMixin):
    __tablename__ = "proposal_comments"

    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"),         nullable=False, index=True)
    author_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"),             nullable=False)
    parent_id   = Column(UUID(as_uuid=True), ForeignKey("proposal_comments.id"), nullable=True)
    body        = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False)

    proposal = relationship("Proposal",        back_populates="comments")
    author   = relationship("User",            back_populates="comments")
    replies  = relationship("ProposalComment", back_populates="parent",
                            foreign_keys="ProposalComment.parent_id")
    parent   = relationship("ProposalComment", back_populates="replies",
                            foreign_keys="ProposalComment.parent_id",
                            remote_side="ProposalComment.id")


class ProposalStatusLog(Base, BaseModelMixin):
    __tablename__ = "proposal_status_logs"

    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    from_status = Column(Enum(ProposalStatus), nullable=True)
    to_status   = Column(Enum(ProposalStatus), nullable=False)
    changed_by  = Column(UUID(as_uuid=True),   ForeignKey("users.id"),  nullable=False)
    reason      = Column(Text, nullable=True)

    proposal        = relationship("Proposal", back_populates="status_logs")
    changed_by_user = relationship("User",     foreign_keys=[changed_by])
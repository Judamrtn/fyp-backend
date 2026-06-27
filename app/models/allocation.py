import enum
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class AllocationStatus(str, enum.Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SupervisorAllocation(Base, BaseModelMixin):
    __tablename__ = "supervisor_allocations"

    proposal_id      = Column(UUID(as_uuid=True), ForeignKey("proposals.id"),      nullable=False, unique=True)
    student_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"),           nullable=False)
    supervisor_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),           nullable=False)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)
    status           = Column(Enum(AllocationStatus), default=AllocationStatus.ACTIVE)

    proposal        = relationship("Proposal",     back_populates="allocation")
    student         = relationship("User",         foreign_keys=[student_id])
    supervisor_user = relationship("User",         foreign_keys=[supervisor_id])
    academic_year   = relationship("AcademicYear", back_populates="allocations")


class ProjectRegistration(Base, BaseModelMixin):
    __tablename__ = "project_registrations"

    proposal_id = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, unique=False)
    title       = Column(String(500), nullable=False)
    abstract    = Column(Text, nullable=True)
    is_public   = Column(Boolean, default=True)
    is_seeded   = Column(Boolean, default=False)

    proposal       = relationship("Proposal", back_populates="registration",
                                  foreign_keys=[proposal_id])
    research_areas = relationship("ProjectResearchArea", back_populates="project")


class ProjectResearchArea(Base, BaseModelMixin):
    __tablename__ = "project_research_areas"

    project_id       = Column(UUID(as_uuid=True), ForeignKey("project_registrations.id"), nullable=False)
    research_area_id = Column(UUID(as_uuid=True), ForeignKey("research_areas.id"),        nullable=False)

    project       = relationship("ProjectRegistration", back_populates="research_areas")
    research_area = relationship("ResearchArea",        back_populates="project_areas")
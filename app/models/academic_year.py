from sqlalchemy import Column, String, Boolean, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class AcademicYear(Base, BaseModelMixin):
    __tablename__ = "academic_years"

    label      = Column(String(50), unique=True, nullable=False)   # e.g. "2024/2025"
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=False)
    is_active  = Column(Boolean, default=False)

    proposals  = relationship("Proposal",           back_populates="academic_year")
    deadlines  = relationship("SubmissionDeadline", back_populates="academic_year")
    allocations = relationship("SupervisorAllocation", back_populates="academic_year")


class SubmissionDeadline(Base, BaseModelMixin):
    __tablename__ = "submission_deadlines"

    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=False)
    department_id    = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    open_date        = Column(Date, nullable=False)
    close_date       = Column(Date, nullable=False)

    academic_year = relationship("AcademicYear", back_populates="deadlines")
    department    = relationship("Department",   back_populates="deadlines")

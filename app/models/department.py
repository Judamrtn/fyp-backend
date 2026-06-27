from sqlalchemy import Column, String, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class Faculty(Base, BaseModelMixin):
    __tablename__ = "faculties"

    name        = Column(String(200), unique=True, nullable=False)
    code        = Column(String(20),  unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active   = Column(Boolean, default=True)

    departments = relationship("Department", back_populates="faculty")


class Department(Base, BaseModelMixin):
    __tablename__ = "departments"

    faculty_id  = Column(UUID(as_uuid=True), ForeignKey("faculties.id"), nullable=False)
    name        = Column(String(200), nullable=False)
    code        = Column(String(20),  nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active   = Column(Boolean, default=True)

    faculty          = relationship("Faculty",          back_populates="departments")
    hod_profile      = relationship("HODProfile",       back_populates="department", uselist=False)
    programs         = relationship("Program",          back_populates="department")
    supervisors      = relationship("SupervisorProfile", back_populates="department")
    proposals        = relationship("Proposal",         back_populates="department")
    research_areas   = relationship("ResearchArea",     back_populates="department")
    similarity_config = relationship("SimilarityConfig", back_populates="department", uselist=False)
    deadlines        = relationship("SubmissionDeadline", back_populates="department")


class Program(Base, BaseModelMixin):
    __tablename__ = "programs"

    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=False)
    name          = Column(String(200), nullable=False)
    code          = Column(String(20),  nullable=False, unique=True)
    description   = Column(Text, nullable=True)
    is_active     = Column(Boolean, default=True)

    department = relationship("Department", back_populates="programs")
    students   = relationship("StudentProfile", back_populates="program")


class ResearchArea(Base, BaseModelMixin):
    __tablename__ = "research_areas"

    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    name          = Column(String(200), nullable=False)
    description   = Column(Text, nullable=True)
    is_active     = Column(Boolean, default=True)

    department    = relationship("Department",       back_populates="research_areas")
    project_areas = relationship("ProjectResearchArea", back_populates="research_area")
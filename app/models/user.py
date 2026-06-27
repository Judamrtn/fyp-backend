import enum
from sqlalchemy import (
    Column, String, Boolean, Enum, Integer, ForeignKey, Text, Date
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class UserRole(str, enum.Enum):
    STUDENT    = "student"
    SUPERVISOR = "supervisor"
    HOD        = "hod"
    ADMIN      = "admin"


class Gender(str, enum.Enum):
    MALE   = "male"
    FEMALE = "female"
    OTHER  = "other"


class User(Base, BaseModelMixin):
    __tablename__ = "users"

    # Common fields
    email         = Column(String(255), unique=True, nullable=True, index=True)  # nullable for students
    regno         = Column(String(50),  unique=True, nullable=True, index=True)  # students only
    password_hash = Column(String(255), nullable=False)
    first_name    = Column(String(100), nullable=False)
    last_name     = Column(String(100), nullable=False)
    role          = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    is_active     = Column(Boolean, default=True, nullable=False)
    phone         = Column(String(30), nullable=True)
    profile_image = Column(String(500), nullable=True)

    # Force password change on first login
    must_change_password = Column(Boolean, default=False, nullable=False)

    # Password reset
    reset_token            = Column(String(255), nullable=True)
    reset_token_expires_at = Column(String(50),  nullable=True)

    # Relationships
    student_profile    = relationship("StudentProfile",    back_populates="user", uselist=False)
    supervisor_profile = relationship("SupervisorProfile", back_populates="user", uselist=False)
    proposals          = relationship("Proposal",          back_populates="student",
                                      foreign_keys="Proposal.student_id")
    comments           = relationship("ProposalComment",   back_populates="author")
    notifications      = relationship("Notification",      back_populates="user")
    activity_logs      = relationship("ActivityLog",       back_populates="actor")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def username(self) -> str:
        """Login identifier — regno for students, email for others."""
        return self.regno if self.role == UserRole.STUDENT else self.email

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"


class StudentProfile(Base, BaseModelMixin):
    __tablename__ = "student_profiles"

    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    program_id      = Column(UUID(as_uuid=True), ForeignKey("programs.id"), nullable=True)
    enrollment_year = Column(Integer, nullable=True)
    gender          = Column(Enum(Gender), nullable=True)
    date_of_birth   = Column(Date, nullable=True)

    user    = relationship("User",    back_populates="student_profile")
    program = relationship("Program", back_populates="students")


class SupervisorProfile(Base, BaseModelMixin):
    __tablename__ = "supervisor_profiles"

    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    department_id    = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    max_students     = Column(Integer, default=5, nullable=False)
    current_students = Column(Integer, default=0, nullable=False)
    specializations  = Column(Text, nullable=True)

    user       = relationship("User",       back_populates="supervisor_profile")
    department = relationship("Department", back_populates="supervisors")

    @property
    def is_at_capacity(self) -> bool:
        return self.current_students >= self.max_students


class HODProfile(Base, BaseModelMixin):
    __tablename__ = "hod_profiles"

    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"),       unique=True, nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), unique=True, nullable=True)

    user       = relationship("User",       backref="hod_profile", uselist=False)
    department = relationship("Department", back_populates="hod_profile", uselist=False)
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import date
from app.models.user import UserRole, Gender


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """
    Students login with regno, others with email.
    We use a single 'username' field that accepts both.
    """
    username: str   # regno for students, email for others
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


# ── Admin creates HOD ─────────────────────────────────────────────────────────

class CreateHODRequest(BaseModel):
    email:         EmailStr
    password:      str
    first_name:    str
    last_name:     str
    phone:         Optional[str] = None
    department_id: str


# ── HOD creates Supervisor ────────────────────────────────────────────────────

class CreateSupervisorRequest(BaseModel):
    email:           EmailStr
    password:        str
    first_name:      str
    last_name:       str
    phone:           Optional[str] = None
    specializations: Optional[str] = None
    max_students:    int = 5


# ── HOD creates Student ───────────────────────────────────────────────────────

class CreateStudentRequest(BaseModel):
    regno:           str
    first_name:      str
    last_name:       str
    email:           Optional[EmailStr] = None
    phone:           Optional[str] = None
    program_id:      str
    enrollment_year: Optional[int] = None
    gender:          Optional[Gender] = None
    date_of_birth:   Optional[date] = None


# ── HOD bulk imports students via CSV row ─────────────────────────────────────

class StudentCSVRow(BaseModel):
    regno:           str
    first_name:      str
    last_name:       str
    email:           Optional[str] = None
    phone:           Optional[str] = None
    program_code:    str             # matched against programs in HOD's department
    enrollment_year: Optional[int] = None
    gender:          Optional[str] = None
    date_of_birth:   Optional[str] = None


# ── Forgot / Reset password ───────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


# ── Responses ─────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"


class UserOut(BaseModel):
    id:                   str
    email:                Optional[str] = None
    regno:                Optional[str] = None
    first_name:           str
    last_name:            str
    role:                 UserRole
    is_active:            bool
    phone:                Optional[str] = None
    must_change_password: bool = False

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user:  UserOut
    token: TokenResponse


# ── Refresh ───────────────────────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str
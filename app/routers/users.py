from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
import uuid
import re

from app.database import get_db
from app.schemas import ok
from app.schemas.auth import (
    CreateSupervisorRequest, CreateStudentRequest,
)
from app.models.user import User, UserRole, SupervisorProfile, StudentProfile
from app.dependencies import get_current_user, require_roles
from app.services.auth_service import auth_service
from app.utils.storage import storage

router = APIRouter()


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    phone:      Optional[str] = None


class PasswordStrengthCheck(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def check_strength(cls, v: str) -> str:
        errors = []
        if len(v) < 8:
            errors.append("at least 8 characters")
        if not re.search(r"[A-Z]", v):
            errors.append("at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            errors.append("at least one lowercase letter")
        if not re.search(r"\d", v):
            errors.append("at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            errors.append("at least one special character")
        if errors:
            raise ValueError(f"Password must contain: {', '.join(errors)}")
        return v


@router.get("/me", summary="Get current user profile")
def get_profile(user: User = Depends(get_current_user)):
    data = {
        "id":                   str(user.id),
        "email":                user.email,
        "regno":                user.regno,
        "first_name":           user.first_name,
        "last_name":            user.last_name,
        "full_name":            user.full_name,
        "role":                 user.role,
        "phone":                user.phone,
        "profile_image":        user.profile_image,
        "must_change_password": user.must_change_password,
    }

    # Add role-specific profile info
    if user.role == UserRole.STUDENT and user.student_profile:
        sp = user.student_profile
        data["student_profile"] = {
            "program_id":      str(sp.program_id) if sp.program_id else None,
            "program_name":    sp.program.name if sp.program else None,
            "enrollment_year": sp.enrollment_year,
            "gender":          sp.gender,
        }

    if user.role == UserRole.SUPERVISOR and user.supervisor_profile:
        sp = user.supervisor_profile
        data["supervisor_profile"] = {
            "department_id":    str(sp.department_id) if sp.department_id else None,
            "department_name":  sp.department.name if sp.department else None,
            "max_students":     sp.max_students,
            "current_students": sp.current_students,
            "specializations":  sp.specializations,
            "is_at_capacity":   sp.is_at_capacity,
        }

    return ok(data=data)


@router.patch("/me", summary="Update profile")
def update_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return ok(message="Profile updated.")


@router.post("/me/profile-image", summary="Upload profile image")
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Only image files are allowed.")

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:  # 5MB max
        raise HTTPException(400, "Image must be under 5MB.")

    storage_key  = storage.upload(file_bytes, file.filename, file.content_type)
    signed_url   = storage.get_signed_url(storage_key)

    user.profile_image = signed_url
    db.commit()

    return ok(data={"profile_image": signed_url}, message="Profile image updated.")


# ── Supervisor profile (visible to students) ──────────────────────────────────

@router.get("/supervisors/{supervisor_id}",
            summary="View supervisor profile (accessible to students)")
def get_supervisor_profile(
    supervisor_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    supervisor = db.query(User).filter(
        User.id   == supervisor_id,
        User.role == UserRole.SUPERVISOR,
        User.deleted_at.is_(None),
        User.is_active == True,
    ).first()
    if not supervisor:
        raise HTTPException(404, "Supervisor not found.")

    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == supervisor_id
    ).first()

    # Count approved projects supervised
    from app.models.proposal import Proposal, ProposalStatus
    supervised_count = db.query(Proposal).filter(
        Proposal.supervisor_id == supervisor_id,
        Proposal.status.in_([
            ProposalStatus.APPROVED,
            ProposalStatus.UNDER_SUPERVISION,
        ]),
        Proposal.deleted_at.is_(None),
    ).count()

    return ok(data={
        "id":               str(supervisor.id),
        "name":             supervisor.full_name,
        "email":            supervisor.email,
        "profile_image":    supervisor.profile_image,
        "department":       profile.department.name if profile and profile.department else None,
        "specializations":  profile.specializations if profile else None,
        "max_students":     profile.max_students    if profile else 5,
        "current_students": profile.current_students if profile else 0,
        "is_at_capacity":   profile.is_at_capacity  if profile else False,
        "supervised_projects": supervised_count,
    })


@router.get("/supervisors", summary="List all supervisors (public to logged in users)")
def list_all_supervisors(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    supervisors = db.query(User).filter(
        User.role      == UserRole.SUPERVISOR,
        User.is_active == True,
        User.deleted_at.is_(None),
    ).all()

    result = []
    for s in supervisors:
        profile = s.supervisor_profile
        result.append({
            "id":               str(s.id),
            "name":             s.full_name,
            "email":            s.email,
            "department":       profile.department.name if profile and profile.department else None,
            "specializations":  profile.specializations if profile else None,
            "is_at_capacity":   profile.is_at_capacity  if profile else False,
            "current_students": profile.current_students if profile else 0,
            "max_students":     profile.max_students    if profile else 5,
        })

    return ok(data=result)


# ── HOD creates Supervisor ────────────────────────────────────────────────────

@router.post("/create-supervisor", summary="HOD creates a supervisor account")
def create_supervisor(
    data: CreateSupervisorRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.HOD)),
):
    user = auth_service.create_supervisor(db, data, actor)
    return ok(data=user.model_dump(), message="Supervisor account created successfully.")


# ── HOD creates Student (single) ──────────────────────────────────────────────

@router.post("/create-student", summary="HOD creates a single student account")
def create_student(
    data: CreateStudentRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.HOD)),
):
    user = auth_service.create_student(db, data, actor)
    return ok(
        data=user.model_dump(),
        message="Student created. Default password is their regno."
    )


# ── HOD bulk imports Students via CSV ─────────────────────────────────────────

@router.post("/import-students", summary="HOD bulk imports students from CSV")
async def import_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.HOD)),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted.")

    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV file must be UTF-8 encoded.")

    result = auth_service.import_students_csv(db, csv_text, actor)
    return ok(
        data=result,
        message=f"Import complete. {result['created']} created, {result['skipped']} skipped."
    )


# ── Password strength check ───────────────────────────────────────────────────

@router.post("/check-password-strength",
             summary="Check password strength before setting it")
def check_password_strength(data: PasswordStrengthCheck):
    """
    Validates password strength:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """
    return ok(data={"strong": True}, message="Password is strong.")


# ── Supervisor updates own profile ────────────────────────────────────────────

class SupervisorProfileUpdate(BaseModel):
    specializations: Optional[str] = None
    max_students:    Optional[int]  = None
    phone:           Optional[str]  = None
    first_name:      Optional[str]  = None
    last_name:       Optional[str]  = None


@router.patch("/me/supervisor-profile",
              summary="Supervisor updates their own profile")
def update_supervisor_profile(
    data: SupervisorProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == user.id
    ).first()
    if not profile:
        raise HTTPException(404, "Supervisor profile not found.")

    if data.specializations is not None:
        profile.specializations = data.specializations
    if data.max_students is not None:
        if data.max_students < profile.current_students:
            raise HTTPException(
                400,
                f"Cannot set max_students below current count ({profile.current_students})."
            )
        profile.max_students = data.max_students
    if data.phone is not None:
        user.phone = data.phone
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name

    db.commit()
    return ok(message="Supervisor profile updated.")


# ── HOD updates supervisor capacity ──────────────────────────────────────────

class SupervisorCapacityUpdate(BaseModel):
    max_students: int


@router.patch("/supervisors/{supervisor_id}/capacity",
              summary="HOD updates supervisor max student capacity")
def update_supervisor_capacity(
    supervisor_id: uuid.UUID,
    data: SupervisorCapacityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == supervisor_id
    ).first()
    if not profile:
        raise HTTPException(404, "Supervisor profile not found.")

    if data.max_students < profile.current_students:
        raise HTTPException(
            400,
            f"Cannot set max_students below current count ({profile.current_students})."
        )

    profile.max_students = data.max_students
    db.commit()
    return ok(message=f"Supervisor capacity updated to {data.max_students}.")


# ── CSV template download ─────────────────────────────────────────────────────

from fastapi.responses import StreamingResponse
import io as _io


@router.get("/import-students/template",
            summary="Download CSV template for student bulk import")
def download_csv_template(
    user: User = Depends(require_roles(UserRole.HOD)),
):
    """
    Returns a CSV template file with the correct headers for bulk student import.
    Columns: regno, first_name, last_name, email, phone, program_code,
             enrollment_year, gender, date_of_birth
    """
    headers = [
        "regno", "first_name", "last_name", "email", "phone",
        "program_code", "enrollment_year", "gender", "date_of_birth"
    ]
    example = [
        "CS/2024/001", "Alice", "Brown", "alice@university.edu",
        "0712345678", "BCS", "2024", "female", "2002-05-14"
    ]

    content  = ",".join(headers) + "\n"
    content += ",".join(example) + "\n"

    return StreamingResponse(
        _io.StringIO(content),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=student_import_template.csv"
        },
    )
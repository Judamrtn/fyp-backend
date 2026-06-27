from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.schemas import ok
from app.schemas.auth import (
    CreateSupervisorRequest, CreateStudentRequest,
)
from app.models.user import User, UserRole
from app.dependencies import get_current_user, require_roles
from app.services.auth_service import auth_service

router = APIRouter()


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    phone:      Optional[str] = None


@router.get("/me", summary="Get current user profile")
def get_profile(user: User = Depends(get_current_user)):
    return ok(data={
        "id":                   str(user.id),
        "email":                user.email,
        "regno":                user.regno,
        "first_name":           user.first_name,
        "last_name":            user.last_name,
        "role":                 user.role,
        "phone":                user.phone,
        "must_change_password": user.must_change_password,
    })


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
    return ok(data=user.model_dump(), message="Student account created. Default password is their regno.")


# ── HOD bulk imports Students via CSV ─────────────────────────────────────────

@router.post("/import-students", summary="HOD bulk imports students from CSV file")
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
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.academic_year import AcademicYear, SubmissionDeadline
from app.models.user import User, UserRole
from app.dependencies import require_roles, get_current_user

router = APIRouter()


class AcademicYearCreate(BaseModel):
    label:      str
    start_date: date
    end_date:   date
    is_active:  bool = False


class AcademicYearUpdate(BaseModel):
    label:      Optional[str]  = None
    start_date: Optional[date] = None
    end_date:   Optional[date] = None


@router.get("/", summary="List all academic years")
def list_years(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    years = db.query(AcademicYear).filter(
        AcademicYear.deleted_at.is_(None)
    ).order_by(AcademicYear.start_date.desc()).all()

    return ok(data=[
        {
            "id":         str(y.id),
            "label":      y.label,
            "start_date": str(y.start_date),
            "end_date":   str(y.end_date),
            "is_active":  y.is_active,
        }
        for y in years
    ])


@router.get("/active", summary="Get current active academic year")
def get_active_year(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    year = db.query(AcademicYear).filter(
        AcademicYear.is_active    == True,
        AcademicYear.deleted_at.is_(None),
    ).first()
    if not year:
        return ok(data=None, message="No active academic year configured.")
    return ok(data={
        "id":         str(year.id),
        "label":      year.label,
        "start_date": str(year.start_date),
        "end_date":   str(year.end_date),
        "is_active":  year.is_active,
    })


@router.post("/", summary="Create academic year (Admin only)")
def create_year(
    data: AcademicYearCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    # If setting as active, deactivate others first
    if data.is_active:
        db.query(AcademicYear).update({"is_active": False})

    year = AcademicYear(**data.model_dump())
    db.add(year)
    db.commit()
    db.refresh(year)
    return ok(data={
        "id":    str(year.id),
        "label": year.label,
    }, message="Academic year created.")


@router.patch("/{year_id}", summary="Update academic year (Admin only)")
def update_year(
    year_id: uuid.UUID,
    data: AcademicYearUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(404, "Academic year not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(year, k, v)
    db.commit()
    db.refresh(year)
    return ok(data={"id": str(year.id), "label": year.label}, message="Updated.")


@router.patch("/{year_id}/set-active", summary="Set academic year as active (Admin only)")
def set_active_year(
    year_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    # Deactivate all
    db.query(AcademicYear).update({"is_active": False})
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(404, "Academic year not found.")
    year.is_active = True
    db.commit()
    return ok(message=f"'{year.label}' set as active academic year.")


@router.delete("/{year_id}", summary="Delete academic year (Admin only)")
def delete_year(
    year_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(404, "Academic year not found.")
    if year.is_active:
        raise HTTPException(400, "Cannot delete the active academic year.")
    year.soft_delete()
    db.commit()
    return ok(message="Academic year deleted.")
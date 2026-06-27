from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.academic_year import AcademicYear
from app.models.user import UserRole
from app.dependencies import require_roles, get_current_user

router = APIRouter()


class AcademicYearCreate(BaseModel):
    label:      str
    start_date: date
    end_date:   date
    is_active:  bool = False


@router.get("/")
def list_years(db: Session = Depends(get_db), _=Depends(get_current_user)):
    years = db.query(AcademicYear).filter(AcademicYear.deleted_at.is_(None)).all()
    return ok(data=[{"id": str(y.id), "label": y.label, "is_active": y.is_active} for y in years])


@router.post("/")
def create_year(
    data: AcademicYearCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.ADMIN)),
):
    year = AcademicYear(**data.model_dump())
    db.add(year); db.commit(); db.refresh(year)
    return ok(data={"id": str(year.id), "label": year.label}, message="Academic year created.")


@router.patch("/{year_id}/set-active")
def set_active_year(
    year_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=Depends(require_roles(UserRole.ADMIN)),
):
    # Deactivate all, then activate the target
    db.query(AcademicYear).update({"is_active": False})
    year = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not year:
        raise HTTPException(404, "Academic year not found.")
    year.is_active = True
    db.commit()
    return ok(message=f"'{year.label}' set as active academic year.")

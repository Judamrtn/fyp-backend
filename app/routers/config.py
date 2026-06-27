"""
System configuration endpoints.
- Similarity threshold per department (Admin)
- Global settings
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.similarity import SimilarityConfig
from app.models.department import Department
from app.models.user import User, UserRole
from app.dependencies import require_roles

router = APIRouter()


class ThresholdUpdate(BaseModel):
    department_id: Optional[uuid.UUID] = None   # None = global default
    threshold:     int

    @field_validator("threshold")
    @classmethod
    def valid_threshold(cls, v: int) -> int:
        if not 1 <= v <= 100:
            raise ValueError("Threshold must be between 1 and 100.")
        return v


@router.get("/similarity-thresholds", summary="List all similarity thresholds")
def list_thresholds(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.HOD)),
):
    configs = db.query(SimilarityConfig).filter(
        SimilarityConfig.deleted_at.is_(None)
    ).all()
    return ok(data=[
        {
            "id":            str(c.id),
            "department_id": str(c.department_id) if c.department_id else None,
            "threshold":     c.threshold,
        }
        for c in configs
    ])


@router.post("/similarity-thresholds", summary="Set similarity threshold (Admin only)")
def set_threshold(
    data: ThresholdUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    if data.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(404, "Department not found.")

    # Upsert — update if exists, create if not
    existing = db.query(SimilarityConfig).filter(
        SimilarityConfig.department_id == data.department_id
    ).first()

    if existing:
        existing.threshold = data.threshold
        db.commit()
        return ok(
            data={"department_id": str(data.department_id), "threshold": data.threshold},
            message="Threshold updated."
        )
    else:
        config = SimilarityConfig(
            department_id = data.department_id,
            threshold     = data.threshold,
        )
        db.add(config)
        db.commit()
        return ok(
            data={"department_id": str(data.department_id) if data.department_id else "global",
                  "threshold": data.threshold},
            message="Threshold set."
        )
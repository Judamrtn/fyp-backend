from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.deadline import DeadlineCreate, DeadlineUpdate, DeadlineOut
from app.models.academic_year import SubmissionDeadline
from app.models.user import User, UserRole
from app.dependencies import require_roles, get_current_user

router = APIRouter()


@router.get("/", summary="List all submission deadlines")
def list_deadlines(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(SubmissionDeadline).filter(
        SubmissionDeadline.deleted_at.is_(None)
    ).all()
    return ok(data=[DeadlineOut.model_validate(d).model_dump() for d in items])


@router.post("/", summary="Admin or HOD creates a submission deadline")
def create_deadline(
    data: DeadlineCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.HOD)),
):
    # HOD can only set deadline for their own department
    if user.role == UserRole.HOD:
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
        if not hod:
            raise HTTPException(400, "HOD profile not found.")
        if data.department_id and str(data.department_id) != str(hod.department_id):
            raise HTTPException(403, "You can only set deadlines for your own department.")
        data = data.model_copy(update={"department_id": hod.department_id})

    deadline = SubmissionDeadline(**data.model_dump())
    db.add(deadline)
    db.commit()
    db.refresh(deadline)
    return ok(data=DeadlineOut.model_validate(deadline).model_dump(),
              message="Submission deadline created.")


@router.patch("/{deadline_id}", summary="Update a submission deadline")
def update_deadline(
    deadline_id: uuid.UUID,
    data: DeadlineUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.HOD)),
):
    deadline = db.query(SubmissionDeadline).filter(
        SubmissionDeadline.id == deadline_id,
        SubmissionDeadline.deleted_at.is_(None),
    ).first()
    if not deadline:
        raise HTTPException(404, "Deadline not found.")

    for k, v in data.model_dump(exclude_none=True).items():
        setattr(deadline, k, v)

    db.commit()
    db.refresh(deadline)
    return ok(data=DeadlineOut.model_validate(deadline).model_dump())


@router.delete("/{deadline_id}", summary="Delete a submission deadline")
def delete_deadline(
    deadline_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.HOD)),
):
    deadline = db.query(SubmissionDeadline).filter(
        SubmissionDeadline.id == deadline_id
    ).first()
    if not deadline:
        raise HTTPException(404, "Deadline not found.")
    deadline.soft_delete()
    db.commit()
    return ok(message="Deadline deleted.")
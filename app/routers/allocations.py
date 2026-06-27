from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.allocation import SupervisorAllocation
from app.models.user import User, UserRole, SupervisorProfile
from app.models.proposal import Proposal, ProposalStatus
from app.models.academic_year import AcademicYear
from app.dependencies import require_roles

router = APIRouter()


class AllocateRequest(BaseModel):
    proposal_id:   uuid.UUID
    supervisor_id: uuid.UUID


@router.post("/", summary="HOD assigns a supervisor to a proposal")
def allocate_supervisor(
    data: AllocateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    proposal = db.query(Proposal).filter(Proposal.id == data.proposal_id).first()
    if not proposal:
        raise HTTPException(404, "Proposal not found.")

    # Allow assignment from pending onwards
    allowed_statuses = {
        ProposalStatus.PENDING,
        ProposalStatus.UNDER_REVIEW,
        ProposalStatus.SUPERVISOR_APPROVED,
        ProposalStatus.APPROVED,
    }
    if proposal.status not in allowed_statuses:
        raise HTTPException(
            400,
            f"Cannot assign supervisor to a proposal with status: {proposal.status}"
        )

    # Check supervisor capacity
    sup_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == data.supervisor_id
    ).first()
    if not sup_profile:
        raise HTTPException(404, "Supervisor profile not found.")
    if sup_profile.is_at_capacity:
        raise HTTPException(
            400,
            f"Supervisor has reached max student capacity ({sup_profile.max_students})."
        )

    # Check if already allocated
    existing = db.query(SupervisorAllocation).filter(
        SupervisorAllocation.proposal_id == data.proposal_id
    ).first()
    if existing:
        raise HTTPException(400, "A supervisor is already assigned to this proposal.")

    active_year = db.query(AcademicYear).filter(AcademicYear.is_active == True).first()
    if not active_year:
        raise HTTPException(400, "No active academic year.")

    allocation = SupervisorAllocation(
        proposal_id      = data.proposal_id,
        student_id       = proposal.student_id,
        supervisor_id    = data.supervisor_id,
        academic_year_id = active_year.id,
    )
    db.add(allocation)

    proposal.supervisor_id = data.supervisor_id
    sup_profile.current_students += 1

    db.commit()
    return ok(message="Supervisor allocated successfully.")


@router.get("/supervisors", summary="List supervisors with capacity info")
def list_supervisors(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    profiles = db.query(SupervisorProfile).filter(
        SupervisorProfile.deleted_at.is_(None)
    ).all()
    return ok(data=[
        {
            "user_id":          str(p.user_id),
            "name":             p.user.full_name if p.user else "N/A",
            "department_id":    str(p.department_id) if p.department_id else None,
            "max_students":     p.max_students,
            "current_students": p.current_students,
            "is_at_capacity":   p.is_at_capacity,
            "specializations":  p.specializations,
        }
        for p in profiles
    ])
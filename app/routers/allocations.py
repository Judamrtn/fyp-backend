from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.allocation import SupervisorAllocation
from app.models.user import User, UserRole, SupervisorProfile
from app.models.proposal import Proposal, ProposalStatus
from app.models.allocation import SupervisorAllocation
from app.models.academic_year import AcademicYear
from app.dependencies import require_roles

router = APIRouter()


class AllocateRequest(BaseModel):
    proposal_id:  uuid.UUID
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
    if proposal.status != ProposalStatus.SUPERVISOR_APPROVED:
        raise HTTPException(400, "Supervisor can only be assigned to supervisor-approved proposals.")

    sup_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == data.supervisor_id
    ).first()
    if not sup_profile:
        raise HTTPException(404, "Supervisor profile not found.")
    if sup_profile.is_at_capacity:
        raise HTTPException(400, f"Supervisor has reached max student capacity ({sup_profile.max_students}).")

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
    data = [
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
    ]
    return ok(data=data)


@router.get("/supervisors/available",
            summary="List supervisors with available capacity (HOD)")
def list_available_supervisors(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    """Returns supervisors who still have capacity for more students."""
    from app.models.user import SupervisorProfile
    profiles = db.query(SupervisorProfile).filter(
        SupervisorProfile.deleted_at.is_(None),
    ).all()

    available = [
        {
            "user_id":          str(p.user_id),
            "name":             p.user.full_name if p.user else "N/A",
            "email":            p.user.email if p.user else None,
            "department":       p.department.name if p.department else None,
            "max_students":     p.max_students,
            "current_students": p.current_students,
            "available_slots":  p.max_students - p.current_students,
            "specializations":  p.specializations,
        }
        for p in profiles
        if not p.is_at_capacity
    ]

    return ok(data=available)


@router.delete("/{proposal_id}", summary="Remove supervisor allocation (HOD only)")
def remove_allocation(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    from app.models.allocation import SupervisorAllocation
    from app.models.user import SupervisorProfile

    allocation = db.query(SupervisorAllocation).filter(
        SupervisorAllocation.proposal_id == proposal_id
    ).first()
    if not allocation:
        raise HTTPException(404, "No allocation found for this proposal.")

    # Decrease supervisor count
    sup_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == allocation.supervisor_id
    ).first()
    if sup_profile and sup_profile.current_students > 0:
        sup_profile.current_students -= 1

    # Clear supervisor from proposal
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if proposal:
        proposal.supervisor_id = None

    allocation.soft_delete()
    db.commit()
    return ok(message="Supervisor allocation removed.")
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from app.models.proposal import Proposal
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.proposal import (
    ProposalCreate, ProposalUpdate, ProposalStatusUpdate,
    ProposalOut, ProposalObjectivesUpdate,
)
from app.services.proposal_service import proposal_service
from app.dependencies import get_current_user, require_roles
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/")
def list_proposals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = proposal_service.list_for_user(db, user)
    return ok(data=[ProposalOut.model_validate(p).model_dump() for p in items])


@router.post("/")
def create_proposal(
    data: ProposalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = proposal_service.create(db, data, user)
    return ok(data=ProposalOut.model_validate(p).model_dump(), message="Draft created.")


@router.get("/search/all", summary="Search proposals (HOD/Admin)")
def search_proposals(
    q:             str  = Query(None),
    status:        str  = Query(None),
    department_id: str  = Query(None),
    supervisor_id: str  = Query(None),
    flagged:       bool = Query(None),
    page:          int  = Query(1, ge=1),
    limit:         int  = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    from app.models.proposal import ProposalStatus

    query = db.query(Proposal).filter(Proposal.deleted_at.is_(None))

    if user.role == UserRole.HOD:
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
        if hod:
            query = query.filter(Proposal.department_id == hod.department_id)

    if q:
        term = f"%{q.lower()}%"
        query = query.filter(
            Proposal.title.ilike(term) |
            Proposal.abstract.ilike(term) |
            Proposal.keywords.ilike(term)
        )
    if status:
        try:
            query = query.filter(Proposal.status == ProposalStatus(status))
        except ValueError:
            pass
    if department_id:
        query = query.filter(Proposal.department_id == department_id)
    if supervisor_id:
        query = query.filter(Proposal.supervisor_id == supervisor_id)
    if flagged is not None:
        query = query.filter(Proposal.similarity_flag == flagged)

    total = query.count()
    items = query.order_by(Proposal.created_at.desc())\
                 .offset((page - 1) * limit).limit(limit).all()

    return ok(data={
        "total": total,
        "page":  page,
        "pages": (total + limit - 1) // limit,
        "items": [ProposalOut.model_validate(p).model_dump() for p in items],
    })


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = proposal_service.get_for_user(db, proposal_id, user)
    return ok(data=ProposalOut.model_validate(p).model_dump())


@router.patch("/{proposal_id}")
def update_proposal(
    proposal_id: uuid.UUID,
    data: ProposalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = proposal_service.update(db, proposal_id, data, user)
    return ok(data=ProposalOut.model_validate(p).model_dump())


@router.put("/{proposal_id}/objectives", summary="Set objectives (min 3, max 5)")
def set_objectives(
    proposal_id: uuid.UUID,
    data: ProposalObjectivesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = proposal_service.set_objectives(db, proposal_id, data, user)
    return ok(
        data=ProposalOut.model_validate(p).model_dump(),
        message=f"{len(data.objectives)} objectives saved."
    )


@router.post("/{proposal_id}/submit")
def submit_proposal(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = proposal_service.submit(db, proposal_id, user, background_tasks)
    return ok(
        data=ProposalOut.model_validate(p).model_dump(),
        message="Submitted. Similarity check running in background."
    )


@router.patch("/{proposal_id}/status")
def update_status(
    proposal_id: uuid.UUID,
    data: ProposalStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.HOD)),
):
    p = proposal_service.update_status(db, proposal_id, data.status, user, data.reason)
    return ok(data=ProposalOut.model_validate(p).model_dump(), message="Status updated.")


@router.post("/{proposal_id}/withdraw")
def withdraw_proposal(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = proposal_service.withdraw(db, proposal_id, user)
    return ok(data=ProposalOut.model_validate(p).model_dump(), message="Proposal withdrawn.")


@router.get("/{proposal_id}/versions", summary="View proposal version history")
def get_versions(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    versions = proposal_service.get_versions(db, proposal_id, user)
    return ok(data=[
        {
            "version_number": v.version_number,
            "title":          v.title,
            "abstract":       v.abstract,
            "keywords":       v.keywords,
            "objectives":     v.objectives,
            "snapshot_at":    v.snapshot_at,
        }
        for v in versions
    ])


@router.get("/{proposal_id}/status-log", summary="View full status history")
def get_status_log(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = proposal_service.get_for_user(db, proposal_id, user)
    return ok(data=[
        {
            "from_status": str(log.from_status) if log.from_status else None,
            "to_status":   str(log.to_status),
            "changed_by":  str(log.changed_by),
            "reason":      log.reason,
            "timestamp":   str(log.created_at),
        }
        for log in p.status_logs
    ])
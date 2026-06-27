from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.similarity import SimilarityCheck
from app.models.proposal import Proposal
from app.models.user import User, UserRole
from app.dependencies import get_current_user, require_roles

router = APIRouter()


class OverrideRequest(BaseModel):
    justification: str


@router.get("/{proposal_id}/similarity")
def get_similarity(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    check = (
        db.query(SimilarityCheck)
        .filter(SimilarityCheck.proposal_id == proposal_id)
        .order_by(SimilarityCheck.created_at.desc())
        .first()
    )
    if not check:
        return ok(data=None, message="Similarity check not yet completed.")

    return ok(data={
        "score":          check.score,
        "top_matches":    check.top_matches,
        "threshold_used": check.threshold_used,
        "flagged":        check.score >= check.threshold_used,
        "overridden":     check.overridden,
        "override_note":  check.override_note,
    })


@router.post("/{proposal_id}/similarity/override")
def override_similarity_flag(
    proposal_id: uuid.UUID,
    data: OverrideRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.HOD)),
):
    if not data.justification or len(data.justification.strip()) < 10:
        raise HTTPException(400, "A written justification (min 10 chars) is required.")

    check = (
        db.query(SimilarityCheck)
        .filter(SimilarityCheck.proposal_id == proposal_id)
        .order_by(SimilarityCheck.created_at.desc())
        .first()
    )
    if not check:
        raise HTTPException(404, "No similarity check found for this proposal.")

    check.overridden     = True
    check.override_note  = data.justification.strip()
    check.overridden_by  = user.id

    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if proposal:
        proposal.similarity_flag = False   # clear flag after override

    db.commit()
    return ok(message="Similarity flag overridden.")


@router.post("/{proposal_id}/similarity/recheck")
def recheck_similarity(
    proposal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    from app.background.similarity_task import run_similarity_check
    background_tasks.add_task(run_similarity_check, str(proposal_id))
    return ok(message="Similarity re-check queued.")

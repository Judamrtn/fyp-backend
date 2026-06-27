"""
Phase 2 — Project supervision endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.project import (
    MilestoneCreate, MilestoneUpdate, MilestoneOut,
    ProgressCreate, ProgressOut,
    FeedbackCreate, FeedbackOut,
    FeedbackReplyCreate, FeedbackReplyOut,
    MessageCreate, MessageOut,
    RecommendationCreate, RecommendationReview, RecommendationOut,
)
from app.services.project_service import project_service
from app.models.user import User, UserRole
from app.dependencies import get_current_user, require_roles

router = APIRouter()


# ── Milestones ────────────────────────────────────────────────────────────────

@router.get("/{proposal_id}/milestones")
def list_milestones(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = project_service.list_milestones(db, proposal_id, user)
    return ok(data=[MilestoneOut.model_validate(m).model_dump() for m in items])


@router.post("/{proposal_id}/milestones", summary="Supervisor creates a milestone")
def create_milestone(
    proposal_id: uuid.UUID,
    data: MilestoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    m = project_service.create_milestone(db, proposal_id, data, user)
    return ok(data=MilestoneOut.model_validate(m).model_dump(), message="Milestone created.")


@router.patch("/milestones/{milestone_id}", summary="Supervisor updates a milestone")
def update_milestone(
    milestone_id: uuid.UUID,
    data: MilestoneUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    m = project_service.update_milestone(db, milestone_id, data, user)
    return ok(data=MilestoneOut.model_validate(m).model_dump())


@router.delete("/milestones/{milestone_id}", summary="Supervisor deletes a milestone")
def delete_milestone(
    milestone_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    project_service.delete_milestone(db, milestone_id, user)
    return ok(message="Milestone deleted.")


# ── Progress ──────────────────────────────────────────────────────────────────

@router.get("/{proposal_id}/progress")
def list_progress(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = project_service.list_progress(db, proposal_id, user)
    return ok(data=[ProgressOut.model_validate(p).model_dump() for p in items])


@router.post("/{proposal_id}/progress", summary="Student submits a progress update")
def submit_progress(
    proposal_id: uuid.UUID,
    data: ProgressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    p = project_service.submit_progress(db, proposal_id, data, user)
    return ok(data=ProgressOut.model_validate(p).model_dump(), message="Progress submitted.")


# ── Feedback ──────────────────────────────────────────────────────────────────

@router.post("/progress/{progress_id}/feedback", summary="Supervisor gives feedback")
def add_feedback(
    progress_id: uuid.UUID,
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    f = project_service.add_feedback(db, progress_id, data, user)
    return ok(data=FeedbackOut.model_validate(f).model_dump(), message="Feedback added.")


@router.post("/feedback/{feedback_id}/reply", summary="Reply to feedback (student or supervisor)")
def reply_to_feedback(
    feedback_id: uuid.UUID,
    data: FeedbackReplyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reply = project_service.reply_to_feedback(db, feedback_id, data, user)
    return ok(data=FeedbackReplyOut.model_validate(reply).model_dump(), message="Reply sent.")


# ── Supervision Messages ──────────────────────────────────────────────────────

@router.get("/{proposal_id}/messages", summary="Get supervision chat messages")
def list_messages(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = project_service.list_messages(db, proposal_id, user)
    return ok(data=[MessageOut.model_validate(m).model_dump() for m in items])


@router.post("/{proposal_id}/messages", summary="Send a supervision message")
def send_message(
    proposal_id: uuid.UUID,
    data: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    msg = project_service.send_message(db, proposal_id, data, user)
    return ok(data=MessageOut.model_validate(msg).model_dump(), message="Message sent.")


@router.get("/{proposal_id}/messages/unread-count", summary="Get unread message count")
def unread_count(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = project_service.unread_message_count(db, proposal_id, user)
    return ok(data={"unread_count": count})


# ── Defence Recommendation ────────────────────────────────────────────────────

@router.post("/{proposal_id}/recommend-defence", summary="Supervisor recommends for defence")
def create_recommendation(
    proposal_id: uuid.UUID,
    data: RecommendationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    rec = project_service.create_recommendation(db, proposal_id, data, user)
    return ok(
        data=RecommendationOut.model_validate(rec).model_dump(),
        message="Defence recommendation submitted to HOD."
    )


@router.patch("/{proposal_id}/recommend-defence", summary="HOD reviews defence recommendation")
def review_recommendation(
    proposal_id: uuid.UUID,
    data: RecommendationReview,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    rec = project_service.review_recommendation(db, proposal_id, data, user)
    return ok(
        data=RecommendationOut.model_validate(rec).model_dump(),
        message=f"Recommendation {rec.status}."
    )


@router.get("/{proposal_id}/recommend-defence", summary="Get defence recommendation")
def get_recommendation(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rec = project_service.get_recommendation(db, proposal_id, user)
    if not rec:
        return ok(data=None, message="No recommendation submitted yet.")
    return ok(data=RecommendationOut.model_validate(rec).model_dump())
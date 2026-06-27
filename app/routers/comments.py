from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.proposal import CommentCreate, CommentOut
from app.models.proposal import ProposalComment, Proposal
from app.models.user import User, UserRole
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/{proposal_id}/comments")
def list_comments(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ProposalComment).filter(
        ProposalComment.proposal_id == proposal_id,
        ProposalComment.parent_id.is_(None),   # top-level only; client nests replies
    )
    # Students can't see internal comments
    if user.role == UserRole.STUDENT:
        q = q.filter(ProposalComment.is_internal == False)

    comments = q.order_by(ProposalComment.created_at).all()
    return ok(data=[_comment_with_replies(c, user) for c in comments])


@router.post("/{proposal_id}/comments")
def add_comment(
    proposal_id: uuid.UUID,
    data: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(404, "Proposal not found.")

    # Students cannot post internal comments
    if user.role == UserRole.STUDENT and data.is_internal:
        raise HTTPException(403, "Students cannot post internal comments.")

    comment = ProposalComment(
        proposal_id = proposal_id,
        author_id   = user.id,
        body        = data.body,
        is_internal = data.is_internal,
        parent_id   = data.parent_id,
    )
    db.add(comment); db.commit(); db.refresh(comment)
    return ok(data=CommentOut.model_validate(comment).model_dump(), message="Comment added.")


def _comment_with_replies(comment: ProposalComment, user: User) -> dict:
    d = CommentOut.model_validate(comment).model_dump()
    replies = [r for r in comment.replies
               if not (r.is_internal and user.role == UserRole.STUDENT)]
    d["replies"] = [_comment_with_replies(r, user) for r in replies]
    return d

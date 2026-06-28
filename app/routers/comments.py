"""
Proposal comments — threaded, with internal flag.
Used during proposal review phase only.
For supervision phase, use /projects/{id}/messages instead.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.proposal import CommentCreate, CommentOut
from app.models.proposal import ProposalComment, Proposal, ProposalStatus
from app.models.user import User, UserRole
from app.dependencies import get_current_user

router = APIRouter()

# Statuses where comments are allowed
COMMENTABLE_STATUSES = {
    ProposalStatus.PENDING,
    ProposalStatus.UNDER_REVIEW,
    ProposalStatus.SUPERVISOR_APPROVED,
    ProposalStatus.REVISION_REQUIRED,
}


@router.get("/{proposal_id}/comments", summary="List comments on a proposal")
def list_comments(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ProposalComment).filter(
        ProposalComment.proposal_id == proposal_id,
        ProposalComment.parent_id.is_(None),
        ProposalComment.deleted_at.is_(None),
    )
    # Students cannot see internal comments
    if user.role == UserRole.STUDENT:
        q = q.filter(ProposalComment.is_internal == False)

    comments = q.order_by(ProposalComment.created_at).all()
    return ok(data=[_comment_with_replies(c, user) for c in comments])


@router.post("/{proposal_id}/comments", summary="Add a comment to a proposal")
def add_comment(
    proposal_id: uuid.UUID,
    data: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    proposal = db.query(Proposal).filter(
        Proposal.id == proposal_id,
        Proposal.deleted_at.is_(None),
    ).first()
    if not proposal:
        raise HTTPException(404, "Proposal not found.")

    # Students cannot post internal comments
    if user.role == UserRole.STUDENT and data.is_internal:
        raise HTTPException(403, "Students cannot post internal comments.")

    # Students can only comment on their own proposal
    if user.role == UserRole.STUDENT and str(proposal.student_id) != str(user.id):
        raise HTTPException(403, "You can only comment on your own proposal.")

    # Supervisors can only comment on assigned proposals
    if user.role == UserRole.SUPERVISOR and str(proposal.supervisor_id) != str(user.id):
        raise HTTPException(403, "This proposal is not assigned to you.")

    comment = ProposalComment(
        proposal_id = proposal_id,
        author_id   = user.id,
        body        = data.body,
        is_internal = data.is_internal,
        parent_id   = data.parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Notify student if comment is not internal and not from student
    if not data.is_internal and user.role != UserRole.STUDENT:
        from app.services.notification_service import notification_service
        from app.models.notification import NotificationType
        notification_service._create(
            db, proposal.student_id,
            NotificationType.COMMENT_ADDED,
            "New comment on your proposal",
            f"{user.full_name} commented on your proposal.",
            link=f"/proposals/{proposal_id}",
        )
        db.commit()

    return ok(
        data=CommentOut.model_validate(comment).model_dump(),
        message="Comment added."
    )


@router.delete("/{proposal_id}/comments/{comment_id}",
               summary="Delete a comment (author only)")
def delete_comment(
    proposal_id: uuid.UUID,
    comment_id:  uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = db.query(ProposalComment).filter(
        ProposalComment.id          == comment_id,
        ProposalComment.proposal_id == proposal_id,
        ProposalComment.deleted_at.is_(None),
    ).first()
    if not comment:
        raise HTTPException(404, "Comment not found.")
    if str(comment.author_id) != str(user.id):
        raise HTTPException(403, "You can only delete your own comments.")

    comment.soft_delete()
    db.commit()
    return ok(message="Comment deleted.")


def _comment_with_replies(comment: ProposalComment, user: User) -> dict:
    d = CommentOut.model_validate(comment).model_dump()
    replies = [
        r for r in comment.replies
        if not r.deleted_at and
        not (r.is_internal and user.role == UserRole.STUDENT)
    ]
    d["replies"] = [_comment_with_replies(r, user) for r in replies]
    return d
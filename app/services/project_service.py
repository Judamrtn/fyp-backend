"""
Phase 2 project supervision service — with full notifications.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.proposal import Proposal, ProposalStatus
from app.models.project import (
    ProjectMilestone, ProjectProgress, ProgressFeedback, FeedbackReply,
    SupervisionMessage, DefenceRecommendation,
    ProgressStatus, RecommendationStatus,
)
from app.models.user import User, UserRole
from app.schemas.project import (
    MilestoneCreate, MilestoneUpdate,
    ProgressCreate, FeedbackCreate, FeedbackReplyCreate,
    MessageCreate, RecommendationCreate, RecommendationReview,
)
from app.services.notification_service import notification_service


class ProjectService:

    # ── Milestones ────────────────────────────────────────────────────────────

    def create_milestone(self, db: Session, proposal_id: uuid.UUID,
                         data: MilestoneCreate, supervisor: User) -> ProjectMilestone:
        proposal = self._get_active_proposal(db, proposal_id)
        self._assert_supervisor(proposal, supervisor)

        m = ProjectMilestone(
            proposal_id = proposal.id,
            created_by  = supervisor.id,
            title       = data.title,
            description = data.description,
            due_date    = data.due_date,
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return m

    def update_milestone(self, db: Session, milestone_id: uuid.UUID,
                         data: MilestoneUpdate, supervisor: User) -> ProjectMilestone:
        m = self._get_milestone_or_404(db, milestone_id)
        self._assert_supervisor(m.proposal, supervisor)

        for k, v in data.model_dump(exclude_none=True).items():
            setattr(m, k, v)
        if data.is_completed:
            m.completed_at = datetime.now(tz=timezone.utc).isoformat()

        db.commit()
        db.refresh(m)
        return m

    def list_milestones(self, db: Session, proposal_id: uuid.UUID,
                        user: User) -> List[ProjectMilestone]:
        self._assert_access(db, proposal_id, user)
        return db.query(ProjectMilestone).filter(
            ProjectMilestone.proposal_id == proposal_id,
            ProjectMilestone.deleted_at.is_(None),
        ).order_by(ProjectMilestone.created_at).all()

    def delete_milestone(self, db: Session, milestone_id: uuid.UUID,
                         supervisor: User) -> None:
        m = self._get_milestone_or_404(db, milestone_id)
        self._assert_supervisor(m.proposal, supervisor)
        m.soft_delete()
        db.commit()

    # ── Progress ──────────────────────────────────────────────────────────────

    def submit_progress(self, db: Session, proposal_id: uuid.UUID,
                        data: ProgressCreate, student: User) -> ProjectProgress:
        proposal = self._get_active_proposal(db, proposal_id)

        if str(proposal.student_id) != str(student.id):
            raise HTTPException(403, "This is not your proposal.")
        if not data.document_url and not data.description:
            raise HTTPException(400, "Either a document URL or description is required.")

        p = ProjectProgress(
            proposal_id   = proposal.id,
            milestone_id  = data.milestone_id,
            submitted_by  = student.id,
            title         = data.title,
            description   = data.description,
            document_url  = data.document_url,
            document_type = data.document_type,
            status        = ProgressStatus.SUBMITTED,
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        # Notify supervisor
        notification_service.notify_progress_submitted(db, proposal, data.title)
        db.commit()

        return p

    def list_progress(self, db: Session, proposal_id: uuid.UUID,
                      user: User) -> List[ProjectProgress]:
        self._assert_access(db, proposal_id, user)
        return db.query(ProjectProgress).filter(
            ProjectProgress.proposal_id == proposal_id,
            ProjectProgress.deleted_at.is_(None),
        ).order_by(ProjectProgress.created_at.desc()).all()

    # ── Feedback ──────────────────────────────────────────────────────────────

    def add_feedback(self, db: Session, progress_id: uuid.UUID,
                     data: FeedbackCreate, supervisor: User) -> ProgressFeedback:
        progress = db.query(ProjectProgress).filter(
            ProjectProgress.id == progress_id,
            ProjectProgress.deleted_at.is_(None),
        ).first()
        if not progress:
            raise HTTPException(404, "Progress update not found.")

        self._assert_supervisor(progress.proposal, supervisor)

        f = ProgressFeedback(
            progress_id   = progress.id,
            supervisor_id = supervisor.id,
            feedback_text = data.feedback_text,
            status_update = data.status_update,
        )
        db.add(f)
        progress.status = data.status_update
        db.commit()
        db.refresh(f)

        # Notify student
        notification_service.notify_feedback_given(db, progress.proposal, progress.title)
        db.commit()

        return f

    # ── Feedback Replies ──────────────────────────────────────────────────────

    def reply_to_feedback(self, db: Session, feedback_id: uuid.UUID,
                          data: FeedbackReplyCreate, user: User) -> FeedbackReply:
        feedback = db.query(ProgressFeedback).filter(
            ProgressFeedback.id == feedback_id
        ).first()
        if not feedback:
            raise HTTPException(404, "Feedback not found.")

        proposal    = feedback.progress.proposal
        is_student  = str(proposal.student_id)    == str(user.id)
        is_supervisor = str(proposal.supervisor_id) == str(user.id)

        if not is_student and not is_supervisor:
            raise HTTPException(403, "You are not part of this project.")

        reply = FeedbackReply(
            feedback_id = feedback.id,
            sender_id   = user.id,
            message     = data.message,
        )
        db.add(reply)
        db.commit()
        db.refresh(reply)

        # Notify the other party
        recipient_id = proposal.supervisor_id if is_student else proposal.student_id
        notification_service.notify_feedback_reply(db, proposal, user, recipient_id)
        db.commit()

        return reply

    # ── Supervision Messages ──────────────────────────────────────────────────

    def send_message(self, db: Session, proposal_id: uuid.UUID,
                     data: MessageCreate, user: User) -> SupervisionMessage:
        proposal = self._get_active_proposal(db, proposal_id)

        is_student    = str(proposal.student_id)    == str(user.id)
        is_supervisor = str(proposal.supervisor_id) == str(user.id)

        if not is_student and not is_supervisor:
            raise HTTPException(403, "You are not part of this project.")

        msg = SupervisionMessage(
            proposal_id = proposal.id,
            sender_id   = user.id,
            message     = data.message,
            is_read     = False,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        # Notify the other party
        recipient_id = proposal.supervisor_id if is_student else proposal.student_id
        notification_service.notify_new_message(db, proposal, user, recipient_id)
        db.commit()

        return msg

    def list_messages(self, db: Session, proposal_id: uuid.UUID,
                      user: User) -> List[SupervisionMessage]:
        proposal = self._get_active_proposal(db, proposal_id)

        is_student    = str(proposal.student_id)    == str(user.id)
        is_supervisor = str(proposal.supervisor_id) == str(user.id)

        if not is_student and not is_supervisor:
            raise HTTPException(403, "You are not part of this project.")

        # Mark messages from the other party as read
        other_id = proposal.supervisor_id if is_student else proposal.student_id
        db.query(SupervisionMessage).filter(
            SupervisionMessage.proposal_id == proposal_id,
            SupervisionMessage.sender_id   == other_id,
            SupervisionMessage.is_read     == False,
        ).update({"is_read": True})
        db.commit()

        return db.query(SupervisionMessage).filter(
            SupervisionMessage.proposal_id == proposal_id,
            SupervisionMessage.deleted_at.is_(None),
        ).order_by(SupervisionMessage.created_at).all()

    def unread_message_count(self, db: Session, proposal_id: uuid.UUID,
                             user: User) -> int:
        return db.query(SupervisionMessage).filter(
            SupervisionMessage.proposal_id == proposal_id,
            SupervisionMessage.is_read     == False,
            SupervisionMessage.sender_id   != user.id,
            SupervisionMessage.deleted_at.is_(None),
        ).count()

    # ── Defence Recommendation ────────────────────────────────────────────────

    def create_recommendation(self, db: Session, proposal_id: uuid.UUID,
                               data: RecommendationCreate,
                               supervisor: User) -> DefenceRecommendation:
        proposal = self._get_active_proposal(db, proposal_id)
        self._assert_supervisor(proposal, supervisor)

        existing = db.query(DefenceRecommendation).filter(
            DefenceRecommendation.proposal_id == proposal_id
        ).first()
        if existing:
            raise HTTPException(400, "A recommendation already exists for this proposal.")

        rec = DefenceRecommendation(
            proposal_id         = proposal.id,
            supervisor_id       = supervisor.id,
            recommendation_note = data.recommendation_note,
            status              = RecommendationStatus.PENDING,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        # Notify HOD
        notification_service.notify_recommendation_submitted(db, proposal)
        db.commit()

        return rec

    def review_recommendation(self, db: Session, proposal_id: uuid.UUID,
                               data: RecommendationReview,
                               hod: User) -> DefenceRecommendation:
        rec = db.query(DefenceRecommendation).filter(
            DefenceRecommendation.proposal_id == proposal_id
        ).first()
        if not rec:
            raise HTTPException(404, "No recommendation found for this proposal.")

        rec.status      = data.status
        rec.hod_note    = data.hod_note
        rec.reviewed_by = hod.id
        db.commit()
        db.refresh(rec)

        # Notify student
        notification_service.notify_recommendation_reviewed(
            db, rec.proposal, data.status.value
        )
        db.commit()

        return rec

    def get_recommendation(self, db: Session, proposal_id: uuid.UUID,
                            user: User) -> Optional[DefenceRecommendation]:
        self._assert_access(db, proposal_id, user)
        return db.query(DefenceRecommendation).filter(
            DefenceRecommendation.proposal_id == proposal_id
        ).first()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_active_proposal(self, db: Session, proposal_id: uuid.UUID) -> Proposal:
        proposal = db.query(Proposal).filter(
            Proposal.id == proposal_id,
            Proposal.deleted_at.is_(None),
        ).first()
        if not proposal:
            raise HTTPException(404, "Proposal not found.")
        if proposal.status != ProposalStatus.UNDER_SUPERVISION:
            raise HTTPException(
                400,
                f"Project supervision only available for approved proposals. "
                f"Current status: {proposal.status}"
            )
        return proposal

    def _assert_supervisor(self, proposal: Proposal, supervisor: User):
        if str(proposal.supervisor_id) != str(supervisor.id):
            raise HTTPException(403, "This project is not assigned to you.")

    def _assert_access(self, db: Session, proposal_id: uuid.UUID, user: User):
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(404, "Proposal not found.")
        if user.role == UserRole.STUDENT and str(proposal.student_id) != str(user.id):
            raise HTTPException(403, "Access denied.")
        if user.role == UserRole.SUPERVISOR and str(proposal.supervisor_id) != str(user.id):
            raise HTTPException(403, "This project is not assigned to you.")

    def _get_milestone_or_404(self, db: Session,
                               milestone_id: uuid.UUID) -> ProjectMilestone:
        m = db.query(ProjectMilestone).filter(
            ProjectMilestone.id == milestone_id,
            ProjectMilestone.deleted_at.is_(None),
        ).first()
        if not m:
            raise HTTPException(404, "Milestone not found.")
        return m


project_service = ProjectService()
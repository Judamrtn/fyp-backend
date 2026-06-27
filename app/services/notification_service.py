"""
Notification service — creates in-app notifications for all workflow events.
"""
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType
from app.models.proposal import Proposal, ProposalStatus
from app.models.user import User


class NotificationService:

    def _create(self, db: Session, user_id, ntype: NotificationType,
                title: str, body: str, link: str = None):
        n = Notification(
            user_id = user_id,
            type    = ntype,
            title   = title,
            body    = body,
            link    = link,
        )
        db.add(n)

    # ── Proposal Phase ────────────────────────────────────────────────────────

    def notify_proposal_submitted(self, db: Session, proposal: Proposal):
        """Notify HOD when student submits a proposal."""
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(
            HODProfile.department_id == proposal.department_id
        ).first()
        if hod:
            self._create(
                db, hod.user_id,
                NotificationType.PROPOSAL_SUBMITTED,
                "New proposal submitted",
                f"'{proposal.title[:60]}' has been submitted and awaits your review.",
                link=f"/proposals/{proposal.id}",
            )

    def notify_supervisor_assigned(self, db: Session, proposal: Proposal):
        """Notify supervisor when HOD assigns them to a proposal."""
        if proposal.supervisor_id:
            self._create(
                db, proposal.supervisor_id,
                NotificationType.SUPERVISOR_ASSIGNED,
                "New proposal assigned to you",
                f"You have been assigned to supervise: '{proposal.title[:60]}'",
                link=f"/proposals/{proposal.id}",
            )
            # Also notify student
            self._create(
                db, proposal.student_id,
                NotificationType.SUPERVISOR_ASSIGNED,
                "Supervisor assigned to your proposal",
                "A supervisor has been assigned to your proposal.",
                link=f"/proposals/{proposal.id}",
            )

    def notify_status_change(self, db: Session, proposal: Proposal,
                              new_status: ProposalStatus, actor: User):
        """Notify relevant parties on every status change."""
        STATUS_MAP = {
            ProposalStatus.UNDER_REVIEW: (
                NotificationType.GENERAL,
                "Your proposal is under review",
                proposal.student_id,
            ),
            ProposalStatus.REVISION_REQUIRED: (
                NotificationType.REVISION_REQUESTED,
                "Revision requested on your proposal",
                proposal.student_id,
            ),
            ProposalStatus.SUPERVISOR_APPROVED: (
                NotificationType.SUPERVISOR_FIRST_APPROVAL,
                "Proposal passed supervisor review",
                proposal.student_id,
            ),
            ProposalStatus.APPROVED: (
                NotificationType.PROPOSAL_APPROVED,
                "Your proposal has been approved! 🎉",
                proposal.student_id,
            ),
            ProposalStatus.REJECTED: (
                NotificationType.PROPOSAL_REJECTED,
                "Your proposal was rejected",
                proposal.student_id,
            ),
        }

        if new_status in STATUS_MAP:
            ntype, title, recipient_id = STATUS_MAP[new_status]
            self._create(
                db, recipient_id,
                ntype, title,
                f"Proposal status changed to: {new_status.value}",
                link=f"/proposals/{proposal.id}",
            )

        # Notify HOD when supervisor approves
        if new_status == ProposalStatus.SUPERVISOR_APPROVED:
            from app.models.user import HODProfile
            hod = db.query(HODProfile).filter(
                HODProfile.department_id == proposal.department_id
            ).first()
            if hod:
                self._create(
                    db, hod.user_id,
                    NotificationType.SUPERVISOR_FIRST_APPROVAL,
                    "Proposal ready for final approval",
                    f"'{proposal.title[:60]}' has been approved by supervisor and awaits your final decision.",
                    link=f"/proposals/{proposal.id}",
                )

    # ── Supervision Phase ─────────────────────────────────────────────────────

    def notify_progress_submitted(self, db: Session, proposal: Proposal, progress_title: str):
        """Notify supervisor when student submits a progress update."""
        if proposal.supervisor_id:
            self._create(
                db, proposal.supervisor_id,
                NotificationType.GENERAL,
                "New progress update submitted",
                f"Student submitted: '{progress_title[:60]}'",
                link=f"/projects/{proposal.id}/progress",
            )

    def notify_feedback_given(self, db: Session, proposal: Proposal, progress_title: str):
        """Notify student when supervisor gives feedback."""
        self._create(
            db, proposal.student_id,
            NotificationType.COMMENT_ADDED,
            "Supervisor reviewed your progress",
            f"Feedback received on: '{progress_title[:60]}'",
            link=f"/projects/{proposal.id}/progress",
        )

    def notify_feedback_reply(self, db: Session, proposal: Proposal,
                               sender: User, recipient_id):
        """Notify the other party when someone replies to feedback."""
        self._create(
            db, recipient_id,
            NotificationType.COMMENT_ADDED,
            "New reply on feedback",
            f"{sender.full_name} replied to a feedback thread.",
            link=f"/projects/{proposal.id}/progress",
        )

    def notify_recommendation_submitted(self, db: Session, proposal: Proposal):
        """Notify HOD when supervisor recommends student for defence."""
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(
            HODProfile.department_id == proposal.department_id
        ).first()
        if hod:
            self._create(
                db, hod.user_id,
                NotificationType.GENERAL,
                "Defence recommendation submitted",
                f"Supervisor recommends '{proposal.title[:60]}' for final defence.",
                link=f"/projects/{proposal.id}/recommend-defence",
            )

    def notify_recommendation_reviewed(self, db: Session, proposal: Proposal, status: str):
        """Notify student when HOD approves or rejects defence recommendation."""
        title = "Defence recommendation approved! 🎉" if status == "approved" \
                else "Defence recommendation rejected"
        self._create(
            db, proposal.student_id,
            NotificationType.GENERAL,
            title,
            f"HOD has {status} your defence recommendation.",
            link=f"/projects/{proposal.id}/recommend-defence",
        )

    def notify_new_message(self, db: Session, proposal: Proposal,
                           sender: User, recipient_id):
        """Notify the other party of a new supervision message."""
        self._create(
            db, recipient_id,
            NotificationType.GENERAL,
            f"New message from {sender.full_name}",
            f"You have a new message regarding: '{proposal.title[:60]}'",
            link=f"/projects/{proposal.id}/messages",
        )


notification_service = NotificationService()
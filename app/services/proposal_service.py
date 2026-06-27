"""
Proposal workflow service — Phase 1.

Flow:
  Student submits → PENDING (similarity runs, HOD notified)
  HOD reviews similarity → assigns supervisor (supervisor notified)
  Supervisor reviews content → UNDER_REVIEW → SUPERVISOR_APPROVED / REVISION_REQUIRED
  HOD final decision → APPROVED / REJECTED → UNDER_SUPERVISION
"""
import json
from datetime import datetime, timezone, date
from typing import List, Optional
import uuid

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.models.proposal import (
    Proposal, ProposalStatus, ProposalObjective,
    ProposalVersion, ProposalComment, ProposalStatusLog,
)
from app.models.academic_year import AcademicYear, SubmissionDeadline
from app.models.user import User, UserRole
from app.schemas.proposal import (
    ProposalCreate, ProposalUpdate, CommentCreate,
    ProposalObjectivesUpdate, MIN_OBJECTIVES,
)
from app.services.notification_service import notification_service

STUDENT_EDITABLE_STATUSES = {ProposalStatus.DRAFT, ProposalStatus.REVISION_REQUIRED}

VALID_TRANSITIONS = {
    (ProposalStatus.DRAFT,               UserRole.STUDENT):    {ProposalStatus.PENDING},
    (ProposalStatus.REVISION_REQUIRED,   UserRole.STUDENT):    {ProposalStatus.PENDING},
    (ProposalStatus.DRAFT,               UserRole.STUDENT):    {ProposalStatus.WITHDRAWN},
    (ProposalStatus.PENDING,             UserRole.STUDENT):    {ProposalStatus.WITHDRAWN},
    (ProposalStatus.PENDING,             UserRole.SUPERVISOR): {ProposalStatus.UNDER_REVIEW},
    (ProposalStatus.UNDER_REVIEW,        UserRole.SUPERVISOR): {
        ProposalStatus.REVISION_REQUIRED,
        ProposalStatus.SUPERVISOR_APPROVED,
    },
    (ProposalStatus.SUPERVISOR_APPROVED, UserRole.HOD): {
        ProposalStatus.APPROVED,
        ProposalStatus.REJECTED,
    },
}


class ProposalService:

    def create(self, db: Session, data: ProposalCreate, student: User) -> Proposal:
        active_year = db.query(AcademicYear).filter(AcademicYear.is_active == True).first()
        if not active_year:
            raise HTTPException(400, "No active academic year configured.")

        proposal = Proposal(
            student_id       = student.id,
            department_id    = data.department_id,
            academic_year_id = active_year.id,
            title            = data.title,
            abstract         = data.abstract,
            keywords         = data.keywords,
            status           = ProposalStatus.DRAFT,
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        return proposal

    def update(self, db: Session, proposal_id: uuid.UUID,
               data: ProposalUpdate, student: User) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)
        self._assert_owner(proposal, student)

        if proposal.status not in STUDENT_EDITABLE_STATUSES:
            raise HTTPException(400, f"Cannot edit a proposal in '{proposal.status}' status.")

        for k, v in data.model_dump(exclude_none=True).items():
            setattr(proposal, k, v)

        db.commit()
        db.refresh(proposal)
        return proposal

    def set_objectives(self, db: Session, proposal_id: uuid.UUID,
                       data: ProposalObjectivesUpdate, student: User) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)
        self._assert_owner(proposal, student)

        if proposal.status not in STUDENT_EDITABLE_STATUSES:
            raise HTTPException(400, "Objectives can only be edited in Draft or Revision Required status.")

        db.query(ProposalObjective).filter(
            ProposalObjective.proposal_id == proposal.id
        ).delete()

        for i, text in enumerate(data.objectives, start=1):
            db.add(ProposalObjective(
                proposal_id    = proposal.id,
                objective_text = text,
                order_number   = i,
            ))

        db.commit()
        db.refresh(proposal)
        return proposal

    def submit(self, db: Session, proposal_id: uuid.UUID,
               student: User, background_tasks: BackgroundTasks) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)
        self._assert_owner(proposal, student)

        if proposal.status not in STUDENT_EDITABLE_STATUSES:
            raise HTTPException(400, "Only Draft or Revision Required proposals can be submitted.")

        obj_count = db.query(ProposalObjective).filter(
            ProposalObjective.proposal_id == proposal.id,
            ProposalObjective.deleted_at.is_(None),
        ).count()
        if obj_count < MIN_OBJECTIVES:
            raise HTTPException(
                400,
                f"At least {MIN_OBJECTIVES} objectives required. You have {obj_count}."
            )

        self._check_deadline(db, proposal)

        objectives_snapshot = json.dumps([o.objective_text for o in proposal.objectives])
        latest_version = len(proposal.versions) + 1
        db.add(ProposalVersion(
            proposal_id    = proposal.id,
            version_number = latest_version,
            title          = proposal.title,
            abstract       = proposal.abstract,
            keywords       = proposal.keywords,
            objectives     = objectives_snapshot,
            snapshot_at    = datetime.now(tz=timezone.utc).isoformat(),
        ))

        self._transition(db, proposal, ProposalStatus.PENDING, student)
        proposal.submission_date = datetime.now(tz=timezone.utc).isoformat()
        db.commit()
        db.refresh(proposal)

        # Run similarity check in background
        from app.background.similarity_task import run_similarity_check
        background_tasks.add_task(run_similarity_check, str(proposal.id))

        # Notify HOD
        notification_service.notify_proposal_submitted(db, proposal)
        db.commit()

        return proposal

    def update_status(self, db: Session, proposal_id: uuid.UUID,
                      new_status: ProposalStatus, actor: User,
                      reason: Optional[str] = None) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)

        if actor.role == UserRole.SUPERVISOR:
            if str(proposal.supervisor_id) != str(actor.id):
                raise HTTPException(403, "This proposal is not assigned to you.")

        allowed = VALID_TRANSITIONS.get((proposal.status, actor.role), set())
        if new_status not in allowed:
            raise HTTPException(
                400,
                f"Cannot transition from '{proposal.status}' to '{new_status}' as {actor.role}.",
            )

        if new_status == ProposalStatus.REJECTED and not reason:
            raise HTTPException(400, "A reason is required when rejecting.")

        if new_status == ProposalStatus.APPROVED:
            self._check_similarity_flag(db, proposal)

        self._transition(db, proposal, new_status, actor, reason)

        if new_status == ProposalStatus.APPROVED:
            proposal.approval_date = datetime.now(tz=timezone.utc).isoformat()
            self._create_project_registration(db, proposal)
            proposal.status = ProposalStatus.UNDER_SUPERVISION

        elif new_status == ProposalStatus.REJECTED:
            proposal.rejection_reason = reason

        db.commit()
        db.refresh(proposal)
        notification_service.notify_status_change(db, proposal, new_status, actor)
        db.commit()
        return proposal

    def withdraw(self, db: Session, proposal_id: uuid.UUID, student: User) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)
        self._assert_owner(proposal, student)

        if proposal.status not in {ProposalStatus.DRAFT, ProposalStatus.PENDING}:
            raise HTTPException(400, "Only Draft or Pending proposals can be withdrawn.")

        self._transition(db, proposal, ProposalStatus.WITHDRAWN, student)
        db.commit()
        return proposal

    def get_versions(self, db: Session, proposal_id: uuid.UUID, user: User) -> list:
        proposal = self.get_for_user(db, proposal_id, user)
        return proposal.versions

    def get_for_user(self, db: Session, proposal_id: uuid.UUID, user: User) -> Proposal:
        proposal = self._get_or_404(db, proposal_id)
        if user.role == UserRole.STUDENT and str(proposal.student_id) != str(user.id):
            raise HTTPException(403, "Access denied.")
        if user.role == UserRole.SUPERVISOR and str(proposal.supervisor_id) != str(user.id):
            raise HTTPException(403, "This proposal is not assigned to you.")
        return proposal

    def list_for_user(self, db: Session, user: User) -> List[Proposal]:
        q = db.query(Proposal).filter(Proposal.deleted_at.is_(None))
        if user.role == UserRole.STUDENT:
            q = q.filter(Proposal.student_id == user.id)
        elif user.role == UserRole.SUPERVISOR:
            q = q.filter(Proposal.supervisor_id == user.id)
        elif user.role == UserRole.HOD:
            from app.models.user import HODProfile
            hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
            if hod:
                q = q.filter(Proposal.department_id == hod.department_id)
        return q.order_by(Proposal.created_at.desc()).all()

    def _get_or_404(self, db: Session, proposal_id: uuid.UUID) -> Proposal:
        p = db.query(Proposal).filter(
            Proposal.id == proposal_id,
            Proposal.deleted_at.is_(None),
        ).first()
        if not p:
            raise HTTPException(404, "Proposal not found.")
        return p

    def _assert_owner(self, proposal: Proposal, student: User):
        if str(proposal.student_id) != str(student.id):
            raise HTTPException(403, "You do not own this proposal.")

    def _transition(self, db: Session, proposal: Proposal,
                    new_status: ProposalStatus, actor: User,
                    reason: Optional[str] = None):
        db.add(ProposalStatusLog(
            proposal_id = proposal.id,
            from_status = proposal.status,
            to_status   = new_status,
            changed_by  = actor.id,
            reason      = reason,
        ))
        proposal.status = new_status

    def _check_deadline(self, db: Session, proposal: Proposal):
        today = date.today()
        deadline = db.query(SubmissionDeadline).filter(
            SubmissionDeadline.academic_year_id == proposal.academic_year_id,
            SubmissionDeadline.department_id    == proposal.department_id,
        ).first()
        if deadline:
            if today < deadline.open_date or today > deadline.close_date:
                raise HTTPException(
                    400,
                    f"Submission window is {deadline.open_date} – {deadline.close_date}. "
                    "Submissions are currently closed.",
                )

    def _check_similarity_flag(self, db: Session, proposal: Proposal):
        from app.models.similarity import SimilarityCheck
        check = db.query(SimilarityCheck).filter(
            SimilarityCheck.proposal_id == proposal.id,
        ).order_by(SimilarityCheck.created_at.desc()).first()

        if check and check.score >= check.threshold_used and not check.overridden:
            raise HTTPException(
                400,
                f"Proposal similarity flag ({check.score}% >= {check.threshold_used}%). "
                "Override the flag before approving."
            )

    def _create_project_registration(self, db: Session, proposal: Proposal):
        from app.models.allocation import ProjectRegistration
        db.add(ProjectRegistration(
            proposal_id = proposal.id,
            title       = proposal.title,
            abstract    = proposal.abstract,
            is_public   = True,
            is_seeded   = False,
        ))


proposal_service = ProposalService()
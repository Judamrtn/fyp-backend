from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.proposal import Proposal, ProposalStatus
from app.models.user import User, UserRole, SupervisorProfile
from app.models.allocation import ProjectRegistration
from app.dependencies import require_roles

router = APIRouter()


@router.get("/proposals", summary="Proposal statistics (HOD/Admin)")
def proposals_report(
    department_id: Optional[uuid.UUID] = Query(None),
    status:        Optional[ProposalStatus] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    q = db.query(Proposal).filter(Proposal.deleted_at.is_(None))

    if user.role == UserRole.HOD:
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
        if hod:
            q = q.filter(Proposal.department_id == hod.department_id)
    elif department_id:
        q = q.filter(Proposal.department_id == department_id)

    if status:
        q = q.filter(Proposal.status == status)

    proposals = q.all()
    by_status = {s.value: 0 for s in ProposalStatus}
    for p in proposals:
        by_status[p.status.value] += 1

    flagged = sum(1 for p in proposals if p.similarity_flag)

    return ok(data={
        "total":     len(proposals),
        "by_status": by_status,
        "flagged":   flagged,
    })


@router.get("/supervisors", summary="Supervisor workload report (HOD/Admin)")
def supervisors_report(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    q = db.query(SupervisorProfile).filter(SupervisorProfile.deleted_at.is_(None))

    if user.role == UserRole.HOD:
        from app.models.user import HODProfile
        hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
        if hod:
            q = q.filter(SupervisorProfile.department_id == hod.department_id)

    profiles = q.all()
    return ok(data=[
        {
            "name":             p.user.full_name if p.user else "N/A",
            "email":            p.user.email if p.user else "N/A",
            "current_students": p.current_students,
            "max_students":     p.max_students,
            "capacity_pct":     round(p.current_students / p.max_students * 100, 1)
                                if p.max_students else 0,
            "is_at_capacity":   p.is_at_capacity,
            "specializations":  p.specializations,
        }
        for p in profiles
    ])


@router.get("/dashboard/hod", summary="HOD dashboard stats")
def hod_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    from app.models.user import HODProfile, StudentProfile
    hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
    if not hod:
        return ok(data={})

    dept_id = hod.department_id

    proposals = db.query(Proposal).filter(
        Proposal.department_id == dept_id,
        Proposal.deleted_at.is_(None),
    ).all()

    total_students = db.query(StudentProfile).join(
        "program"
    ).filter(
        Proposal.department_id == dept_id
    ).count()

    supervisors = db.query(SupervisorProfile).filter(
        SupervisorProfile.department_id == dept_id,
        SupervisorProfile.deleted_at.is_(None),
    ).all()

    pending_review    = sum(1 for p in proposals if p.status == ProposalStatus.PENDING)
    under_review      = sum(1 for p in proposals if p.status == ProposalStatus.UNDER_REVIEW)
    approved          = sum(1 for p in proposals if p.status == ProposalStatus.APPROVED
                            or p.status == ProposalStatus.UNDER_SUPERVISION)
    rejected          = sum(1 for p in proposals if p.status == ProposalStatus.REJECTED)
    flagged           = sum(1 for p in proposals if p.similarity_flag)
    sup_at_capacity   = sum(1 for s in supervisors if s.is_at_capacity)

    return ok(data={
        "total_proposals":       len(proposals),
        "pending_review":        pending_review,
        "under_review":          under_review,
        "approved":              approved,
        "rejected":              rejected,
        "flagged_similarity":    flagged,
        "total_supervisors":     len(supervisors),
        "supervisors_at_capacity": sup_at_capacity,
    })


@router.get("/dashboard/admin", summary="Admin system-wide stats")
def admin_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    from app.models.user import StudentProfile
    from app.models.department import Department, Faculty

    total_users       = db.query(User).filter(User.deleted_at.is_(None)).count()
    total_students    = db.query(User).filter(User.role == UserRole.STUDENT,
                                              User.deleted_at.is_(None)).count()
    total_supervisors = db.query(User).filter(User.role == UserRole.SUPERVISOR,
                                              User.deleted_at.is_(None)).count()
    total_hods        = db.query(User).filter(User.role == UserRole.HOD,
                                              User.deleted_at.is_(None)).count()
    total_proposals   = db.query(Proposal).filter(Proposal.deleted_at.is_(None)).count()
    total_approved    = db.query(Proposal).filter(
        Proposal.status.in_([ProposalStatus.APPROVED, ProposalStatus.UNDER_SUPERVISION]),
        Proposal.deleted_at.is_(None),
    ).count()
    total_flagged     = db.query(Proposal).filter(
        Proposal.similarity_flag == True,
        Proposal.deleted_at.is_(None),
    ).count()
    total_departments = db.query(Department).filter(Department.deleted_at.is_(None)).count()
    corpus_size       = db.query(ProjectRegistration).filter(
        ProjectRegistration.deleted_at.is_(None),
        ProjectRegistration.is_public == True,
    ).count()

    return ok(data={
        "users": {
            "total":       total_users,
            "students":    total_students,
            "supervisors": total_supervisors,
            "hods":        total_hods,
        },
        "proposals": {
            "total":    total_proposals,
            "approved": total_approved,
            "flagged":  total_flagged,
        },
        "departments":   total_departments,
        "corpus_size":   corpus_size,
    })


@router.get("/dashboard/student", summary="Student dashboard stats")
def student_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.STUDENT)),
):
    from app.models.project import (
        ProjectMilestone, ProjectProgress, SupervisionMessage,
        DefenceRecommendation
    )

    proposals = db.query(Proposal).filter(
        Proposal.student_id  == user.id,
        Proposal.deleted_at.is_(None),
    ).all()

    total             = len(proposals)
    draft             = sum(1 for p in proposals if p.status == ProposalStatus.DRAFT)
    pending           = sum(1 for p in proposals if p.status == ProposalStatus.PENDING)
    under_review      = sum(1 for p in proposals if p.status == ProposalStatus.UNDER_REVIEW)
    approved          = sum(1 for p in proposals if p.status in [
                            ProposalStatus.APPROVED, ProposalStatus.UNDER_SUPERVISION])
    rejected          = sum(1 for p in proposals if p.status == ProposalStatus.REJECTED)
    revision_required = sum(1 for p in proposals if p.status == ProposalStatus.REVISION_REQUIRED)

    # Active project stats
    active_proposal = next(
        (p for p in proposals if p.status == ProposalStatus.UNDER_SUPERVISION), None
    )

    active_project = None
    if active_proposal:
        total_milestones     = db.query(ProjectMilestone).filter(
            ProjectMilestone.proposal_id == active_proposal.id,
            ProjectMilestone.deleted_at.is_(None),
        ).count()
        completed_milestones = db.query(ProjectMilestone).filter(
            ProjectMilestone.proposal_id == active_proposal.id,
            ProjectMilestone.is_completed == True,
            ProjectMilestone.deleted_at.is_(None),
        ).count()
        pending_progress     = db.query(ProjectProgress).filter(
            ProjectProgress.proposal_id == active_proposal.id,
            ProjectProgress.status      == "submitted",
            ProjectProgress.deleted_at.is_(None),
        ).count()
        unread_messages      = db.query(SupervisionMessage).filter(
            SupervisionMessage.proposal_id == active_proposal.id,
            SupervisionMessage.sender_id   != user.id,
            SupervisionMessage.is_read     == False,
            SupervisionMessage.deleted_at.is_(None),
        ).count()
        recommendation = db.query(DefenceRecommendation).filter(
            DefenceRecommendation.proposal_id == active_proposal.id
        ).first()

        active_project = {
            "proposal_id":           str(active_proposal.id),
            "title":                 active_proposal.title,
            "supervisor_id":         str(active_proposal.supervisor_id) if active_proposal.supervisor_id else None,
            "total_milestones":      total_milestones,
            "completed_milestones":  completed_milestones,
            "pending_feedback":      pending_progress,
            "unread_messages":       unread_messages,
            "defence_recommendation": recommendation.status if recommendation else None,
        }

    return ok(data={
        "proposals": {
            "total":            total,
            "draft":            draft,
            "pending":          pending,
            "under_review":     under_review,
            "revision_required": revision_required,
            "approved":         approved,
            "rejected":         rejected,
        },
        "active_project": active_project,
    })


@router.get("/dashboard/supervisor", summary="Supervisor dashboard stats")
def supervisor_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.SUPERVISOR)),
):
    from app.models.project import ProjectProgress, SupervisionMessage, DefenceRecommendation
    from app.models.user import SupervisorProfile

    proposals = db.query(Proposal).filter(
        Proposal.supervisor_id == user.id,
        Proposal.deleted_at.is_(None),
    ).all()

    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == user.id
    ).first()

    pending_review    = sum(1 for p in proposals if p.status == ProposalStatus.PENDING)
    under_review      = sum(1 for p in proposals if p.status == ProposalStatus.UNDER_REVIEW)
    active_projects   = sum(1 for p in proposals if p.status == ProposalStatus.UNDER_SUPERVISION)
    revision_required = sum(1 for p in proposals if p.status == ProposalStatus.REVISION_REQUIRED)

    # Count pending progress updates across all active projects
    active_ids = [p.id for p in proposals if p.status == ProposalStatus.UNDER_SUPERVISION]
    pending_progress = db.query(ProjectProgress).filter(
        ProjectProgress.proposal_id.in_(active_ids),
        ProjectProgress.status      == "submitted",
        ProjectProgress.deleted_at.is_(None),
    ).count() if active_ids else 0

    # Unread messages across all active projects
    unread_messages = db.query(SupervisionMessage).filter(
        SupervisionMessage.proposal_id.in_(active_ids),
        SupervisionMessage.sender_id   != user.id,
        SupervisionMessage.is_read     == False,
        SupervisionMessage.deleted_at.is_(None),
    ).count() if active_ids else 0

    # Pending defence recommendations
    pending_recommendations = db.query(DefenceRecommendation).filter(
        DefenceRecommendation.proposal_id.in_(active_ids),
        DefenceRecommendation.status == "pending",
    ).count() if active_ids else 0

    return ok(data={
        "capacity": {
            "current_students": profile.current_students if profile else 0,
            "max_students":     profile.max_students     if profile else 5,
            "is_at_capacity":   profile.is_at_capacity   if profile else False,
        },
        "proposals": {
            "total":            len(proposals),
            "pending_review":   pending_review,
            "under_review":     under_review,
            "revision_required": revision_required,
            "active_projects":  active_projects,
        },
        "active_projects": {
            "pending_progress":        pending_progress,
            "unread_messages":         unread_messages,
            "pending_recommendations": pending_recommendations,
        },
    })


@router.get("/department/overview", summary="HOD department overview — all students and proposal status")
def department_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD)),
):
    from app.models.user import HODProfile, StudentProfile
    from app.models.department import Program

    hod = db.query(HODProfile).filter(HODProfile.user_id == user.id).first()
    if not hod:
        raise HTTPException(400, "HOD profile not found.")

    dept_id = hod.department_id

    # Get all programs in this department
    programs = db.query(Program).filter(
        Program.department_id == dept_id,
        Program.deleted_at.is_(None),
    ).all()

    program_ids = [p.id for p in programs]

    # Get all students in this department
    students = db.query(StudentProfile).filter(
        StudentProfile.program_id.in_(program_ids),
        StudentProfile.deleted_at.is_(None),
    ).all() if program_ids else []

    # Build student overview
    overview = []
    for s in students:
        student_user = s.user
        if not student_user:
            continue

        # Get their proposals
        proposals = db.query(Proposal).filter(
            Proposal.student_id  == s.user_id,
            Proposal.deleted_at.is_(None),
        ).all()

        latest = proposals[0] if proposals else None

        overview.append({
            "student_id":    str(s.user_id),
            "name":          student_user.full_name,
            "regno":         student_user.regno,
            "program":       s.program.name if s.program else None,
            "enrollment_year": s.enrollment_year,
            "proposal": {
                "id":          str(latest.id) if latest else None,
                "title":       latest.title   if latest else None,
                "status":      latest.status  if latest else None,
                "supervisor":  str(latest.supervisor_id) if latest and latest.supervisor_id else None,
                "flagged":     latest.similarity_flag if latest else False,
            } if latest else None,
        })

    return ok(data={
        "department_id": str(dept_id),
        "total_students": len(students),
        "students": overview,
    })
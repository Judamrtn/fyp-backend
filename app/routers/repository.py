from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.allocation import ProjectRegistration, ProjectResearchArea
from app.models.proposal import Proposal
from app.models.department import ResearchArea
from app.models.user import User, UserRole, SupervisorProfile
from app.dependencies import get_current_user, require_roles

router = APIRouter()


@router.get("/", summary="Browse approved project repository")
def browse_repository(
    department_id:    Optional[uuid.UUID] = Query(None),
    academic_year_id: Optional[uuid.UUID] = Query(None),
    research_area_id: Optional[uuid.UUID] = Query(None),
    supervisor_id:    Optional[uuid.UUID] = Query(None),
    page:  int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(ProjectRegistration)
        .join(Proposal, ProjectRegistration.proposal_id == Proposal.id, isouter=True)
        .filter(
            ProjectRegistration.deleted_at.is_(None),
            ProjectRegistration.is_public == True,
            ProjectRegistration.is_seeded == False,
        )
    )

    if department_id:
        q = q.filter(Proposal.department_id == department_id)
    if academic_year_id:
        q = q.filter(Proposal.academic_year_id == academic_year_id)
    if supervisor_id:
        q = q.filter(Proposal.supervisor_id == supervisor_id)
    if research_area_id:
        q = q.join(ProjectResearchArea,
                   ProjectResearchArea.project_id == ProjectRegistration.id)\
             .filter(ProjectResearchArea.research_area_id == research_area_id)

    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()

    return ok(data={
        "total": total,
        "page":  page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "items": [_reg_out(r) for r in items],
    })


@router.get("/search", summary="Full-text search on title and abstract")
def search_repository(
    q_str:            str  = Query(..., alias="q", min_length=2),
    department_id:    Optional[uuid.UUID] = Query(None),
    academic_year_id: Optional[uuid.UUID] = Query(None),
    supervisor_id:    Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    term = f"%{q_str.lower()}%"
    q = (
        db.query(ProjectRegistration)
        .join(Proposal, ProjectRegistration.proposal_id == Proposal.id, isouter=True)
        .filter(
            ProjectRegistration.deleted_at.is_(None),
            ProjectRegistration.is_public == True,
            ProjectRegistration.is_seeded == False,
        )
        .filter(
            ProjectRegistration.title.ilike(term) |
            ProjectRegistration.abstract.ilike(term)
        )
    )

    if department_id:
        q = q.filter(Proposal.department_id == department_id)
    if academic_year_id:
        q = q.filter(Proposal.academic_year_id == academic_year_id)
    if supervisor_id:
        q = q.filter(Proposal.supervisor_id == supervisor_id)

    results = q.limit(50).all()
    return ok(data={
        "query":   q_str,
        "total":   len(results),
        "results": [_reg_out(r) for r in results],
    })


@router.get("/stats", summary="Repository statistics")
def repository_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from sqlalchemy import func
    from app.models.department import Department
    from app.models.academic_year import AcademicYear

    total = db.query(ProjectRegistration).filter(
        ProjectRegistration.is_public == True,
        ProjectRegistration.is_seeded == False,
        ProjectRegistration.deleted_at.is_(None),
    ).count()

    by_dept = (
        db.query(Department.name, func.count(ProjectRegistration.id))
        .join(Proposal, Proposal.department_id == Department.id)
        .join(ProjectRegistration, ProjectRegistration.proposal_id == Proposal.id)
        .filter(
            ProjectRegistration.is_seeded == False,
            ProjectRegistration.deleted_at.is_(None),
        )
        .group_by(Department.name)
        .all()
    )

    by_year = (
        db.query(AcademicYear.label, func.count(ProjectRegistration.id))
        .join(Proposal, Proposal.academic_year_id == AcademicYear.id)
        .join(ProjectRegistration, ProjectRegistration.proposal_id == Proposal.id)
        .filter(
            ProjectRegistration.is_seeded == False,
            ProjectRegistration.deleted_at.is_(None),
        )
        .group_by(AcademicYear.label)
        .all()
    )

    return ok(data={
        "total_projects":   total,
        "by_department":    [{"name": n, "count": c} for n, c in by_dept],
        "by_academic_year": [{"label": l, "count": c} for l, c in by_year],
    })


@router.get("/{registration_id}", summary="Get full project detail")
def get_project_detail(
    registration_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reg = db.query(ProjectRegistration).filter(
        ProjectRegistration.id        == registration_id,
        ProjectRegistration.is_public == True,
        ProjectRegistration.is_seeded == False,
        ProjectRegistration.deleted_at.is_(None),
    ).first()
    if not reg:
        raise HTTPException(404, "Project not found.")

    proposal   = reg.proposal
    supervisor = None
    department = None
    year       = None

    if proposal:
        if proposal.supervisor_id:
            sup_user    = proposal.supervisor
            sup_profile = db.query(SupervisorProfile).filter(
                SupervisorProfile.user_id == proposal.supervisor_id
            ).first()
            supervisor = {
                "id":              str(proposal.supervisor_id),
                "name":            sup_user.full_name if sup_user else "N/A",
                "email":           sup_user.email if sup_user else None,
                "specializations": sup_profile.specializations if sup_profile else None,
            }
        if proposal.department:
            department = {
                "id":   str(proposal.department_id),
                "name": proposal.department.name,
                "code": proposal.department.code,
            }
        if proposal.academic_year:
            year = {
                "id":    str(proposal.academic_year_id),
                "label": proposal.academic_year.label,
            }

    research_areas = [
        {"id": str(ra.research_area_id), "name": ra.research_area.name}
        for ra in reg.research_areas
        if not ra.deleted_at
    ] if reg.research_areas else []

    return ok(data={
        "id":             str(reg.id),
        "proposal_id":    str(reg.proposal_id) if reg.proposal_id else None,
        "title":          reg.title,
        "abstract":       reg.abstract,
        "research_areas": research_areas,
        "supervisor":     supervisor,
        "department":     department,
        "academic_year":  year,
        "objectives":     [
            {"order": o.order_number, "text": o.objective_text}
            for o in proposal.objectives
        ] if proposal else [],
    })


@router.post("/{registration_id}/research-areas",
             summary="Tag a project with a research area (HOD/Admin)")
def add_research_area(
    registration_id:  uuid.UUID,
    research_area_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    reg = db.query(ProjectRegistration).filter(
        ProjectRegistration.id == registration_id
    ).first()
    if not reg:
        raise HTTPException(404, "Project not found.")

    existing = db.query(ProjectResearchArea).filter(
        ProjectResearchArea.project_id       == registration_id,
        ProjectResearchArea.research_area_id == research_area_id,
    ).first()
    if existing:
        return ok(message="Research area already tagged.")

    db.add(ProjectResearchArea(
        project_id       = registration_id,
        research_area_id = research_area_id,
    ))
    db.commit()
    return ok(message="Research area added.")


@router.delete("/{registration_id}/research-areas/{research_area_id}",
               summary="Remove research area tag (HOD/Admin)")
def remove_research_area(
    registration_id:  uuid.UUID,
    research_area_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN)),
):
    tag = db.query(ProjectResearchArea).filter(
        ProjectResearchArea.project_id       == registration_id,
        ProjectResearchArea.research_area_id == research_area_id,
    ).first()
    if tag:
        tag.soft_delete()
        db.commit()
    return ok(message="Research area removed.")


def _reg_out(r: ProjectRegistration) -> dict:
    research_areas = [
        {"id": str(ra.research_area_id), "name": ra.research_area.name}
        for ra in r.research_areas
        if not ra.deleted_at
    ] if r.research_areas else []

    proposal = r.proposal
    return {
        "id":             str(r.id),
        "proposal_id":    str(r.proposal_id) if r.proposal_id else None,
        "title":          r.title,
        "abstract":       r.abstract,
        "research_areas": research_areas,
        "department":     proposal.department.name if proposal and proposal.department else None,
        "academic_year":  proposal.academic_year.label if proposal and proposal.academic_year else None,
        "supervisor":     proposal.supervisor.full_name if proposal and proposal.supervisor else None,
    }
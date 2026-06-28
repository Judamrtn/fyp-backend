from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.department import (
    FacultyCreate, FacultyOut,
    DepartmentCreate, DepartmentUpdate, DepartmentOut,
    ProgramCreate, ProgramOut,
    ResearchAreaCreate, ResearchAreaOut,
)
from app.models.department import Faculty, Department, Program, ResearchArea
from app.models.user import UserRole, User
from app.dependencies import get_current_user, require_roles

router = APIRouter()
admin_only    = Depends(require_roles(UserRole.ADMIN))
admin_or_hod  = Depends(require_roles(UserRole.ADMIN, UserRole.HOD))


# ── Faculties ─────────────────────────────────────────────────────────────────

@router.get("/faculties", summary="List all faculties")
def list_faculties(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = db.query(Faculty).filter(Faculty.deleted_at.is_(None)).all()
    return ok(data=[FacultyOut.model_validate(f).model_dump() for f in items])


@router.post("/faculties", summary="Create faculty (Admin only)")
def create_faculty(
    data: FacultyCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    if db.query(Faculty).filter(Faculty.code == data.code).first():
        raise HTTPException(400, f"Faculty code '{data.code}' already exists.")
    faculty = Faculty(**data.model_dump())
    db.add(faculty)
    db.commit()
    db.refresh(faculty)
    return ok(data=FacultyOut.model_validate(faculty).model_dump(),
              message="Faculty created.")


@router.patch("/faculties/{faculty_id}", summary="Update faculty (Admin only)")
def update_faculty(
    faculty_id: uuid.UUID,
    data: FacultyCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    f = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not f:
        raise HTTPException(404, "Faculty not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    db.commit()
    db.refresh(f)
    return ok(data=FacultyOut.model_validate(f).model_dump())


@router.delete("/faculties/{faculty_id}", summary="Delete faculty (Admin only)")
def delete_faculty(
    faculty_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=admin_only,
):
    f = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not f:
        raise HTTPException(404, "Faculty not found.")
    f.soft_delete()
    db.commit()
    return ok(message="Faculty deleted.")


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/", summary="List all departments")
def list_departments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = db.query(Department).filter(Department.deleted_at.is_(None)).all()
    return ok(data=[DepartmentOut.model_validate(d).model_dump() for d in items])


@router.get("/{dept_id}", summary="Get department detail")
def get_department(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    dept = db.query(Department).filter(
        Department.id == dept_id,
        Department.deleted_at.is_(None),
    ).first()
    if not dept:
        raise HTTPException(404, "Department not found.")
    return ok(data=DepartmentOut.model_validate(dept).model_dump())


@router.post("/", summary="Create department (Admin only)")
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    if db.query(Department).filter(Department.code == data.code).first():
        raise HTTPException(400, f"Department code '{data.code}' already exists.")

    dept = Department(
        faculty_id  = data.faculty_id,
        name        = data.name,
        code        = data.code,
        description = data.description,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return ok(data=DepartmentOut.model_validate(dept).model_dump(),
              message="Department created.")


@router.patch("/{dept_id}", summary="Update department (Admin only)")
def update_department(
    dept_id: uuid.UUID,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(404, "Department not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    return ok(data=DepartmentOut.model_validate(dept).model_dump())


@router.delete("/{dept_id}", summary="Delete department (Admin only)")
def delete_department(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=admin_only,
):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(404, "Department not found.")
    dept.soft_delete()
    db.commit()
    return ok(message="Department deleted.")


# ── Programs ──────────────────────────────────────────────────────────────────

@router.get("/{dept_id}/programs", summary="List programs in a department")
def list_programs(
    dept_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = db.query(Program).filter(
        Program.department_id == dept_id,
        Program.deleted_at.is_(None),
    ).all()
    return ok(data=[ProgramOut.model_validate(p).model_dump() for p in items])


@router.post("/programs", summary="Create program (Admin only)")
def create_program(
    data: ProgramCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    if db.query(Program).filter(Program.code == data.code).first():
        raise HTTPException(400, f"Program code '{data.code}' already exists.")
    prog = Program(**data.model_dump())
    db.add(prog)
    db.commit()
    db.refresh(prog)
    return ok(data=ProgramOut.model_validate(prog).model_dump(),
              message="Program created.")


@router.patch("/programs/{program_id}", summary="Update program (Admin only)")
def update_program(
    program_id: uuid.UUID,
    data: ProgramCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    prog = db.query(Program).filter(Program.id == program_id).first()
    if not prog:
        raise HTTPException(404, "Program not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(prog, k, v)
    db.commit()
    db.refresh(prog)
    return ok(data=ProgramOut.model_validate(prog).model_dump())


@router.delete("/programs/{program_id}", summary="Delete program (Admin only)")
def delete_program(
    program_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=admin_only,
):
    prog = db.query(Program).filter(Program.id == program_id).first()
    if not prog:
        raise HTTPException(404, "Program not found.")
    prog.soft_delete()
    db.commit()
    return ok(message="Program deleted.")


# ── Research Areas ────────────────────────────────────────────────────────────

@router.get("/research-areas", summary="List all research areas")
def list_research_areas(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = db.query(ResearchArea).filter(
        ResearchArea.deleted_at.is_(None)
    ).all()
    return ok(data=[ResearchAreaOut.model_validate(r).model_dump() for r in items])


@router.post("/research-areas", summary="Create research area (Admin only)")
def create_research_area(
    data: ResearchAreaCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    area = ResearchArea(**data.model_dump())
    db.add(area)
    db.commit()
    db.refresh(area)
    return ok(data=ResearchAreaOut.model_validate(area).model_dump(),
              message="Research area created.")


@router.patch("/research-areas/{area_id}", summary="Update research area (Admin only)")
def update_research_area(
    area_id: uuid.UUID,
    data: ResearchAreaCreate,
    db: Session = Depends(get_db),
    _=admin_only,
):
    area = db.query(ResearchArea).filter(ResearchArea.id == area_id).first()
    if not area:
        raise HTTPException(404, "Research area not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(area, k, v)
    db.commit()
    db.refresh(area)
    return ok(data=ResearchAreaOut.model_validate(area).model_dump())


@router.delete("/research-areas/{area_id}", summary="Delete research area (Admin only)")
def delete_research_area(
    area_id: uuid.UUID,
    db: Session = Depends(get_db),
    _=admin_only,
):
    area = db.query(ResearchArea).filter(ResearchArea.id == area_id).first()
    if not area:
        raise HTTPException(404, "Research area not found.")
    area.soft_delete()
    db.commit()
    return ok(message="Research area deleted.")
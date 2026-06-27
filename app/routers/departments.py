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
from app.models.user import UserRole
from app.dependencies import get_current_user, require_roles

router = APIRouter()
admin_only = Depends(require_roles(UserRole.ADMIN))
admin_or_hod = Depends(require_roles(UserRole.ADMIN, UserRole.HOD))


# ── Faculties ─────────────────────────────────────────────────────────────────

@router.get("/faculties")
def list_faculties(db: Session = Depends(get_db), _=admin_or_hod):
    items = db.query(Faculty).filter(Faculty.deleted_at.is_(None)).all()
    return ok(data=[FacultyOut.model_validate(f).model_dump() for f in items])

@router.post("/faculties")
def create_faculty(data: FacultyCreate, db: Session = Depends(get_db), _=admin_only):
    faculty = Faculty(**data.model_dump())
    db.add(faculty); db.commit(); db.refresh(faculty)
    return ok(data=FacultyOut.model_validate(faculty).model_dump(), message="Faculty created.")

@router.delete("/faculties/{faculty_id}")
def delete_faculty(faculty_id: uuid.UUID, db: Session = Depends(get_db), _=admin_only):
    f = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not f: raise HTTPException(404, "Faculty not found.")
    f.soft_delete(); db.commit()
    return ok(message="Faculty deleted.")


# ── Departments ───────────────────────────────────────────────────────────────

@router.get("/")
def list_departments(db: Session = Depends(get_db), user=Depends(get_current_user)):
    items = db.query(Department).filter(Department.deleted_at.is_(None)).all()
    return ok(data=[DepartmentOut.model_validate(d).model_dump() for d in items])

@router.post("/")
def create_department(data: DepartmentCreate, db: Session = Depends(get_db), _=admin_only):
    dept = Department(
        faculty_id  = data.faculty_id,
        name        = data.name,
        code        = data.code,
        description = data.description,
    )
    db.add(dept); db.commit(); db.refresh(dept)
    return ok(data=DepartmentOut.model_validate(dept).model_dump(), message="Department created.")

@router.patch("/{dept_id}")
def update_department(dept_id: uuid.UUID, data: DepartmentUpdate,
                      db: Session = Depends(get_db), _=admin_only):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept: raise HTTPException(404, "Department not found.")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(dept, k, v)
    db.commit(); db.refresh(dept)
    return ok(data=DepartmentOut.model_validate(dept).model_dump())

@router.delete("/{dept_id}")
def delete_department(dept_id: uuid.UUID, db: Session = Depends(get_db), _=admin_only):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept: raise HTTPException(404, "Department not found.")
    dept.soft_delete(); db.commit()
    return ok(message="Department deleted.")


# ── Programs ──────────────────────────────────────────────────────────────────

@router.get("/{dept_id}/programs")
def list_programs(dept_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(get_current_user)):
    items = db.query(Program).filter(
        Program.department_id == dept_id,
        Program.deleted_at.is_(None),
    ).all()
    return ok(data=[ProgramOut.model_validate(p).model_dump() for p in items])

@router.post("/programs")
def create_program(data: ProgramCreate, db: Session = Depends(get_db), _=admin_only):
    prog = Program(**data.model_dump())
    db.add(prog); db.commit(); db.refresh(prog)
    return ok(data=ProgramOut.model_validate(prog).model_dump(), message="Program created.")


# ── Research Areas ────────────────────────────────────────────────────────────

@router.get("/research-areas")
def list_research_areas(db: Session = Depends(get_db), _=Depends(get_current_user)):
    items = db.query(ResearchArea).filter(ResearchArea.deleted_at.is_(None)).all()
    return ok(data=[ResearchAreaOut.model_validate(r).model_dump() for r in items])

@router.post("/research-areas")
def create_research_area(data: ResearchAreaCreate, db: Session = Depends(get_db), _=admin_only):
    area = ResearchArea(**data.model_dump())
    db.add(area); db.commit(); db.refresh(area)
    return ok(data=ResearchAreaOut.model_validate(area).model_dump(), message="Research area created.")
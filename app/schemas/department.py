from pydantic import BaseModel
from typing import Optional
import uuid


class FacultyCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None

class FacultyOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    faculty_id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None
    hod_id: Optional[uuid.UUID] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    hod_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class DepartmentOut(BaseModel):
    id: uuid.UUID
    faculty_id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class ProgramCreate(BaseModel):
    department_id: uuid.UUID
    name: str
    code: str
    description: Optional[str] = None

class ProgramOut(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    code: str
    is_active: bool

    model_config = {"from_attributes": True}


class ResearchAreaCreate(BaseModel):
    department_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None

class ResearchAreaOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}
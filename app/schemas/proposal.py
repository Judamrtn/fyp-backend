from pydantic import BaseModel
from typing import Optional, List
from app.models.proposal import ProposalStatus
from datetime import datetime
import uuid

MIN_OBJECTIVES = 3
MAX_OBJECTIVES = 5


class ObjectiveIn(BaseModel):
    objective_text: str
    order_number:   int = 1


class ObjectiveOut(BaseModel):
    id:             uuid.UUID
    objective_text: str
    order_number:   int
    model_config = {"from_attributes": True}


class ProposalCreate(BaseModel):
    title:         str
    abstract:      Optional[str] = None
    keywords:      Optional[str] = None
    department_id: uuid.UUID


class ProposalUpdate(BaseModel):
    title:    Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[str] = None


class ProposalObjectivesUpdate(BaseModel):
    objectives: List[str]

    @classmethod
    def validate_count(cls, v):
        v = [o.strip() for o in v if o.strip()]
        if len(v) < MIN_OBJECTIVES:
            raise ValueError(f"At least {MIN_OBJECTIVES} objectives are required.")
        if len(v) > MAX_OBJECTIVES:
            raise ValueError(f"Maximum {MAX_OBJECTIVES} objectives allowed.")
        return v


class ProposalStatusUpdate(BaseModel):
    status: ProposalStatus
    reason: Optional[str] = None


class ProposalOut(BaseModel):
    id:               uuid.UUID
    title:            str
    abstract:         Optional[str] = None
    keywords:         Optional[str] = None
    status:           ProposalStatus
    student_id:       uuid.UUID
    supervisor_id:    Optional[uuid.UUID] = None
    department_id:    uuid.UUID
    academic_year_id: uuid.UUID
    similarity_score: Optional[float] = None
    similarity_flag:  bool
    submission_date:  Optional[str] = None
    approval_date:    Optional[str] = None
    objectives:       List[ObjectiveOut] = []

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body:        str
    parent_id:   Optional[uuid.UUID] = None
    is_internal: bool = False


class CommentOut(BaseModel):
    id:          uuid.UUID
    body:        str
    author_id:   uuid.UUID
    is_internal: bool
    parent_id:   Optional[uuid.UUID] = None
    created_at:  datetime

    model_config = {"from_attributes": True}
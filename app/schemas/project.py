from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
import uuid
from app.models.project import ProgressStatus, DocumentType, RecommendationStatus


# ── Milestones ────────────────────────────────────────────────────────────────

class MilestoneCreate(BaseModel):
    title:       str
    description: Optional[str] = None
    due_date:    Optional[date] = None


class MilestoneUpdate(BaseModel):
    title:        Optional[str]  = None
    description:  Optional[str]  = None
    due_date:     Optional[date] = None
    is_completed: Optional[bool] = None


class MilestoneOut(BaseModel):
    id:           uuid.UUID
    proposal_id:  uuid.UUID
    title:        str
    description:  Optional[str] = None
    due_date:     Optional[date] = None
    is_completed: bool
    completed_at: Optional[str] = None
    created_at:   datetime

    model_config = {"from_attributes": True}


# ── Progress ──────────────────────────────────────────────────────────────────

class ProgressCreate(BaseModel):
    title:         str
    description:   Optional[str] = None
    document_url:  Optional[str] = None
    document_type: Optional[DocumentType] = None
    milestone_id:  Optional[uuid.UUID] = None


class ProgressOut(BaseModel):
    id:            uuid.UUID
    proposal_id:   uuid.UUID
    milestone_id:  Optional[uuid.UUID] = None
    title:         str
    description:   Optional[str] = None
    document_url:  Optional[str] = None
    document_type: Optional[DocumentType] = None
    status:        ProgressStatus
    submitted_by:  uuid.UUID
    created_at:    datetime

    model_config = {"from_attributes": True}


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    feedback_text: str
    status_update: ProgressStatus


class FeedbackReplyCreate(BaseModel):
    message: str


class FeedbackReplyOut(BaseModel):
    id:         uuid.UUID
    message:    str
    sender_id:  uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackOut(BaseModel):
    id:            uuid.UUID
    feedback_text: str
    status_update: ProgressStatus
    supervisor_id: uuid.UUID
    created_at:    datetime
    replies:       List[FeedbackReplyOut] = []

    model_config = {"from_attributes": True}


# ── Supervision Messages ──────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    message: str


class MessageOut(BaseModel):
    id:          uuid.UUID
    proposal_id: uuid.UUID
    sender_id:   uuid.UUID
    message:     str
    is_read:     bool
    created_at:  datetime

    model_config = {"from_attributes": True}


# ── Defence Recommendation ────────────────────────────────────────────────────

class RecommendationCreate(BaseModel):
    recommendation_note: str


class RecommendationReview(BaseModel):
    status:   RecommendationStatus
    hod_note: Optional[str] = None


class RecommendationOut(BaseModel):
    id:                  uuid.UUID
    proposal_id:         uuid.UUID
    supervisor_id:       uuid.UUID
    recommendation_note: str
    status:              RecommendationStatus
    hod_note:            Optional[str] = None
    created_at:          datetime

    model_config = {"from_attributes": True}
from pydantic import BaseModel, field_validator
from datetime import date
from typing import Optional
import uuid


class DeadlineCreate(BaseModel):
    academic_year_id: uuid.UUID
    department_id:    Optional[uuid.UUID] = None   # None = applies to all departments
    open_date:        date
    close_date:       date

    @field_validator("close_date")
    @classmethod
    def close_after_open(cls, v, info):
        if "open_date" in info.data and v <= info.data["open_date"]:
            raise ValueError("close_date must be after open_date.")
        return v


class DeadlineUpdate(BaseModel):
    open_date:  Optional[date] = None
    close_date: Optional[date] = None


class DeadlineOut(BaseModel):
    id:               uuid.UUID
    academic_year_id: uuid.UUID
    department_id:    Optional[uuid.UUID] = None
    open_date:        date
    close_date:       date

    model_config = {"from_attributes": True}
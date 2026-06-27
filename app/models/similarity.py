import enum
from sqlalchemy import Column, Float, Boolean, Text, Integer, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModelMixin


class SimilarityCheck(Base, BaseModelMixin):
    """
    Result of one TF-IDF run.  top_matches is stored as JSONB:
    [{"proposal_id": "...", "title": "...", "score": 0.83}, ...]
    """
    __tablename__ = "similarity_checks"

    proposal_id    = Column(UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True)
    score          = Column(Float, nullable=False)          # 0.0 – 100.0
    top_matches    = Column(JSONB,  nullable=True)          # list of top-5 objects
    threshold_used = Column(Integer, nullable=False, default=80)
    overridden     = Column(Boolean, default=False)
    override_note  = Column(Text, nullable=True)
    overridden_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    proposal       = relationship("Proposal", back_populates="similarity_checks")
    override_user  = relationship("User",     foreign_keys=[overridden_by])


class SimilarityConfig(Base, BaseModelMixin):
    """Per-department threshold; falls back to global default if absent."""
    __tablename__ = "similarity_config"

    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"),
                           nullable=True, unique=True)
    threshold     = Column(Integer, nullable=False, default=80)

    department = relationship("Department", back_populates="similarity_config")

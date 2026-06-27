from app.models.base import BaseModelMixin, UUIDMixin, TimestampMixin, SoftDeleteMixin
from app.models.user import User, UserRole, Gender, StudentProfile, SupervisorProfile, HODProfile
from app.models.department import Faculty, Department, Program, ResearchArea
from app.models.academic_year import AcademicYear, SubmissionDeadline
from app.models.proposal import (
    Proposal, ProposalStatus,
    ProposalObjective,
    ProposalVersion, ProposalDocument,
    ProposalComment, ProposalStatusLog,
)
from app.models.similarity import SimilarityCheck, SimilarityConfig
from app.models.allocation import (
    SupervisorAllocation, AllocationStatus,
    ProjectRegistration, ProjectResearchArea,
)
from app.models.notification import Notification, NotificationType, ActivityLog
from app.models.project import (
    ProjectMilestone, ProjectProgress, ProgressFeedback, FeedbackReply,
    SupervisionMessage, DefenceRecommendation,
    ProgressStatus, DocumentType, RecommendationStatus,
)

__all__ = [
    "BaseModelMixin", "UUIDMixin", "TimestampMixin", "SoftDeleteMixin",
    "User", "UserRole", "Gender", "StudentProfile", "SupervisorProfile", "HODProfile",
    "Faculty", "Department", "Program", "ResearchArea",
    "AcademicYear", "SubmissionDeadline",
    "Proposal", "ProposalStatus",
    "ProposalObjective",
    "ProposalVersion", "ProposalDocument",
    "ProposalComment", "ProposalStatusLog",
    "SimilarityCheck", "SimilarityConfig",
    "SupervisorAllocation", "AllocationStatus",
    "ProjectRegistration", "ProjectResearchArea",
    "Notification", "NotificationType", "ActivityLog",
    "ProjectMilestone", "ProjectProgress", "ProgressFeedback", "FeedbackReply",
    "SupervisionMessage", "DefenceRecommendation",
    "ProgressStatus", "DocumentType", "RecommendationStatus",
]
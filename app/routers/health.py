"""
System health endpoint — Admin only.
Shows DB status, corpus size, HuggingFace API status, active users.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import requests as http_requests

from app.database import get_db
from app.schemas import ok
from app.models.user import User, UserRole
from app.models.allocation import ProjectRegistration
from app.models.notification import ActivityLog
from app.dependencies import require_roles
from app.config import settings

router = APIRouter()


@router.get("/", summary="System health check (Admin only)")
def system_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    # ── Database ──────────────────────────────────────────────────────────────
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # ── Corpus ────────────────────────────────────────────────────────────────
    try:
        corpus_size = db.query(ProjectRegistration).filter(
            ProjectRegistration.deleted_at.is_(None),
            ProjectRegistration.is_public == True,
        ).count()
        seeded_count = db.query(ProjectRegistration).filter(
            ProjectRegistration.deleted_at.is_(None),
            ProjectRegistration.is_seeded == True,
        ).count()
        approved_count = corpus_size - seeded_count
    except Exception:
        corpus_size = seeded_count = approved_count = "error"

    # ── HuggingFace API ───────────────────────────────────────────────────────
    hf_status = "not_configured"
    if settings.hf_api_key and settings.use_ai_similarity:
        try:
            url = f"{settings.hf_api_url}/{settings.hf_model}"
            response = http_requests.post(
                url,
                headers={"Authorization": f"Bearer {settings.hf_api_key}"},
                json={"inputs": ["health check"], "options": {"wait_for_model": True}},
                timeout=10,
            )
            hf_status = "ok" if response.status_code == 200 else f"error: {response.status_code}"
        except Exception as e:
            hf_status = f"error: {str(e)[:50]}"

    # ── Recent activity ───────────────────────────────────────────────────────
    try:
        recent_logs = db.query(ActivityLog).filter(
            ActivityLog.deleted_at.is_(None)
        ).order_by(ActivityLog.created_at.desc()).limit(5).all()
        recent_activity = [
            {"action": log.action, "timestamp": str(log.created_at)}
            for log in recent_logs
        ]
    except Exception:
        recent_activity = []

    return ok(data={
        "status":    "ok" if db_status == "ok" else "degraded",
        "database":  db_status,
        "corpus": {
            "total":    corpus_size,
            "seeded":   seeded_count,
            "approved": approved_count,
            "ready":    corpus_size >= 50 if isinstance(corpus_size, int) else False,
        },
        "huggingface": {
            "status":    hf_status,
            "model":     settings.hf_model,
            "enabled":   settings.use_ai_similarity,
        },
        "similarity_engine": "hybrid" if hf_status == "ok" else "tfidf_only",
        "recent_activity": recent_activity,
    })
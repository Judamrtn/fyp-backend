from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.schemas.auth import CreateHODRequest
from app.models.user import User, UserRole
from app.models.allocation import ProjectRegistration
from app.models.notification import ActivityLog
from app.dependencies import require_roles
from app.services.auth_service import auth_service

router = APIRouter()
admin_only = Depends(require_roles(UserRole.ADMIN))


# ── HOD creation ──────────────────────────────────────────────────────────────

@router.post("/users/create-hod", summary="Admin creates a HOD account")
def create_hod(
    data: CreateHODRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = auth_service.create_hod(db, data, actor)
    _log(db, actor, "user.created_hod", "user", str(user.id))
    return ok(data=user.model_dump(), message="HOD account created successfully.")


# ── User listing & management ─────────────────────────────────────────────────

@router.get("/users", summary="List all users")
def list_users(db: Session = Depends(get_db), _=admin_only):
    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    return ok(data=[
        {
            "id":        str(u.id),
            "username":  u.username,
            "name":      u.full_name,
            "role":      u.role,
            "is_active": u.is_active,
        }
        for u in users
    ])


@router.patch("/users/{user_id}/toggle-active", summary="Activate or deactivate a user")
def toggle_user_active(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found.")
    user.is_active = not user.is_active
    db.commit()
    _log(db, actor, "user.toggled_active", "user", str(user_id),
         {"is_active": user.is_active})
    return ok(message=f"User {'activated' if user.is_active else 'deactivated'}.")


# ── Corpus seeding ────────────────────────────────────────────────────────────

class SeedCorpusRequest(BaseModel):
    titles: List[str]


@router.post("/seed-corpus", summary="Seed similarity corpus with historical titles")
def seed_corpus(
    data: SeedCorpusRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    if not data.titles:
        raise HTTPException(400, "At least 1 title required.")

    added = 0
    for title in data.titles:
        title = title.strip()
        if not title:
            continue
        db.add(ProjectRegistration(
            proposal_id = None,
            title       = title,
            is_public   = True,
            is_seeded   = True,
        ))
        added += 1

    db.commit()
    _log(db, actor, "corpus.seeded", None, None, {"count": added})
    return ok(data={"seeded": added}, message=f"{added} titles added to corpus.")


# ── Activity Logs ─────────────────────────────────────────────────────────────

@router.get("/activity-logs", summary="View system activity logs (Admin only)")
def get_activity_logs(
    limit:  int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _=admin_only,
):
    logs = db.query(ActivityLog).filter(
        ActivityLog.deleted_at.is_(None)
    ).order_by(ActivityLog.created_at.desc()).offset(offset).limit(limit).all()

    return ok(data=[
        {
            "id":          str(log.id),
            "actor":       log.actor.full_name if log.actor else "System",
            "action":      log.action,
            "entity_type": log.entity_type,
            "entity_id":   str(log.entity_id) if log.entity_id else None,
            "extra_data":  log.extra_data,
            "ip_address":  log.ip_address,
            "timestamp":   str(log.created_at),
        }
        for log in logs
    ])


# ── Helper ────────────────────────────────────────────────────────────────────

def _log(db: Session, actor: User, action: str,
         entity_type: Optional[str], entity_id: Optional[str],
         extra_data: dict = None):
    db.add(ActivityLog(
        actor_id    = actor.id,
        action      = action,
        entity_type = entity_type,
        entity_id   = uuid.UUID(entity_id) if entity_id else None,
        extra_data  = extra_data,
    ))
    db.commit()


# ── Bulk actions ──────────────────────────────────────────────────────────────

class BulkUserAction(BaseModel):
    user_ids:  List[uuid.UUID]
    action:    str   # "activate" | "deactivate" | "delete"


@router.post("/users/bulk-action", summary="Bulk activate/deactivate/delete users")
def bulk_user_action(
    data: BulkUserAction,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
):
    if data.action not in ("activate", "deactivate", "delete"):
        raise HTTPException(400, "Action must be: activate, deactivate, or delete.")

    users = db.query(User).filter(User.id.in_(data.user_ids)).all()
    if not users:
        raise HTTPException(404, "No users found.")

    count = 0
    for u in users:
        if u.role == UserRole.ADMIN:
            continue   # Never bulk-action other admins
        if data.action == "activate":
            u.is_active = True
        elif data.action == "deactivate":
            u.is_active = False
        elif data.action == "delete":
            u.soft_delete()
        count += 1

    db.commit()
    _log(db, actor, f"user.bulk_{data.action}", "user", None,
         {"count": count, "action": data.action})

    return ok(
        data={"affected": count},
        message=f"{count} users {data.action}d successfully."
    )


# ── System config ─────────────────────────────────────────────────────────────

@router.get("/system-info", summary="Get system configuration info")
def system_info(
    db: Session = Depends(get_db),
    _=admin_only,
):
    from app.config import settings
    return ok(data={
        "app_name":              settings.app_name,
        "app_env":               settings.app_env,
        "storage_provider":      settings.storage_provider,
        "similarity_engine":     "hybrid" if settings.hf_api_key else "tfidf_only",
        "default_threshold":     settings.default_similarity_threshold,
        "max_file_size_mb":      settings.max_file_size_mb,
        "access_token_minutes":  settings.access_token_expire_minutes,
        "refresh_token_days":    settings.refresh_token_expire_days,
    })
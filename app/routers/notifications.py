from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/", summary="List notifications")
def list_notifications(
    unread_only: bool = Query(False),
    limit:       int  = Query(50, ge=1, le=100),
    offset:      int  = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    q = db.query(Notification).filter(
        Notification.user_id    == user.id,
        Notification.deleted_at.is_(None),
    )
    if unread_only:
        q = q.filter(Notification.is_read == False)

    total = q.count()
    items = q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    return ok(data={
        "total":  total,
        "items":  [_n_out(n) for n in items],
    })


@router.get("/unread-count", summary="Get unread notification count")
def unread_count(
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
        Notification.deleted_at.is_(None),
    ).count()
    return ok(data={"unread_count": count})


@router.patch("/{notification_id}/read", summary="Mark notification as read")
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id      == notification_id,
        Notification.user_id == user.id,
    ).first()
    if n:
        n.is_read = True
        db.commit()
    return ok(message="Marked as read.")


@router.patch("/mark-all-read", summary="Mark all notifications as read")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return ok(message="All notifications marked as read.")


@router.delete("/{notification_id}", summary="Delete a notification")
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id      == notification_id,
        Notification.user_id == user.id,
    ).first()
    if n:
        n.soft_delete()
        db.commit()
    return ok(message="Notification deleted.")


@router.delete("/", summary="Clear all notifications")
def clear_all_notifications(
    db: Session = Depends(get_db),
    user: User  = Depends(get_current_user),
):
    notifications = db.query(Notification).filter(
        Notification.user_id    == user.id,
        Notification.deleted_at.is_(None),
    ).all()
    for n in notifications:
        n.soft_delete()
    db.commit()
    return ok(message=f"Cleared {len(notifications)} notifications.")


def _n_out(n: Notification) -> dict:
    return {
        "id":         str(n.id),
        "type":       n.type,
        "title":      n.title,
        "body":       n.body,
        "is_read":    n.is_read,
        "link":       n.link,
        "created_at": str(n.created_at),
    }
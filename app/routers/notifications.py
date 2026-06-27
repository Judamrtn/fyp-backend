from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.schemas import ok
from app.models.notification import Notification
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/")
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.deleted_at.is_(None))
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return ok(data=[_n_out(n) for n in items])


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
        Notification.deleted_at.is_(None),
    ).count()
    return ok(data={"unread_count": count})


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    ).first()
    if n:
        n.is_read = True
        db.commit()
    return ok(message="Marked as read.")


@router.patch("/mark-all-read")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return ok(message="All notifications marked as read.")


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

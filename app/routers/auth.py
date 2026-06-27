from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ok
from app.schemas.auth import (
    LoginRequest, ChangePasswordRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from app.services.auth_service import auth_service
from app.dependencies import get_current_user
from app.models.user import User
from app.utils.token_blacklist import blacklist_token
from app.utils.rate_limiter import is_rate_limited, get_remaining
from app.utils.security import decode_token
from datetime import datetime, timezone

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", summary="Login — regno for students, email for others")
def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)

    # Rate limit: 5 attempts per minute per IP
    if is_rate_limited(ip, max_requests=5, window_seconds=60):
        remaining = get_remaining(ip, max_requests=5, window_seconds=60)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please wait 1 minute. "
                   f"Remaining attempts: {remaining}"
        )

    result = auth_service.login(db, data)
    return ok(data=result.model_dump(), message="Login successful.")


@router.post("/logout", summary="Logout — invalidate current access token")
def logout(
    request: Request,
    user: User = Depends(get_current_user),
):
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()

    if token:
        # Decode to get expiry time
        payload = decode_token(token)
        exp = payload.get("exp", 0) if payload else 0
        blacklist_token(token, expires_at=float(exp))

    return ok(message="Logged out successfully.")


@router.post("/change-password", summary="Change password (required on first login)")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = auth_service.change_password(db, data, user)
    return ok(message=result["message"])


@router.post("/refresh", summary="Refresh access token")
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    result = auth_service.refresh(db, data)
    return ok(data=result.model_dump(), message="Token refreshed.")


@router.post("/forgot-password", summary="Request password reset link")
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    # Rate limit: 3 reset attempts per 5 minutes
    if is_rate_limited(ip, max_requests=3, window_seconds=300):
        raise HTTPException(
            status_code=429,
            detail="Too many reset attempts. Please wait 5 minutes."
        )
    result = auth_service.forgot_password(db, data)
    return ok(message=result["message"])


@router.post("/reset-password", summary="Reset password using token")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    result = auth_service.reset_password(db, data)
    return ok(message=result["message"])
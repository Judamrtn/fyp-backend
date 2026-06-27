from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.utils.security import decode_token_strict
from app.utils.token_blacklist import is_blacklisted

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token   = credentials.credentials
    payload = decode_token_strict(token, expected_type="access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check blacklist (logout)
    if is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    user = db.query(User).filter(
        User.id == user_id,
        User.deleted_at.is_(None),
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive.")

    return user


def get_current_user_strict(
    user: User = Depends(get_current_user),
) -> User:
    """Blocks access if password change is required."""
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="You must change your password before accessing this resource. "
                   "Use POST /api/v1/auth/change-password."
        )
    return user


def require_roles(*roles: UserRole):
    def _guard(current_user: User = Depends(get_current_user_strict)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user
    return _guard


def get_student(user: User = Depends(require_roles(UserRole.STUDENT))) -> User:
    return user

def get_supervisor(user: User = Depends(require_roles(UserRole.SUPERVISOR))) -> User:
    return user

def get_hod(user: User = Depends(require_roles(UserRole.HOD))) -> User:
    return user

def get_admin(user: User = Depends(require_roles(UserRole.ADMIN))) -> User:
    return user

def get_supervisor_or_hod(
    user: User = Depends(require_roles(UserRole.SUPERVISOR, UserRole.HOD))
) -> User:
    return user

def get_hod_or_admin(
    user: User = Depends(require_roles(UserRole.HOD, UserRole.ADMIN))
) -> User:
    return user
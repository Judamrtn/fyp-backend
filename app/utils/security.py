"""
JWT creation/verification and bcrypt password helpers.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
import re

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh", "reset"]


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """
    Hash password using bcrypt.
    bcrypt has a maximum limit of 72 bytes.
    """
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("Password cannot be longer than 72 bytes")
    
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def check_password_strength(password: str) -> list:
    """
    Returns list of errors. Empty list means password is strong.
    Rules:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one number
      - At least one special character
    """
    errors = []

    if len(password) < 8:
        errors.append("at least 8 characters")

    if not re.search(r"[A-Z]", password):
        errors.append("at least one uppercase letter")

    if not re.search(r"[a-z]", password):
        errors.append("at least one lowercase letter")

    if not re.search(r"\d", password):
        errors.append("at least one number")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("at least one special character (!@#$%^&*)")

    return errors


# ── JWT ───────────────────────────────────────────────────────────────────────

def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(tz=timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def create_access_token(user_id: str, role: str) -> str:
    return _make_token(
        {"sub": user_id, "role": role, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    return _make_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def create_reset_token(user_id: str) -> str:
    return _make_token(
        {"sub": user_id, "type": "reset"},
        timedelta(minutes=settings.reset_token_expire_minutes),
    )


def decode_token(token: str) -> Optional[dict]:
    """
    Returns decoded payload or None if invalid/expired.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None


def decode_token_strict(token: str, expected_type: TokenType) -> Optional[dict]:
    """
    Decode and enforce token type.
    """
    payload = decode_token(token)

    if payload and payload.get("type") == expected_type:
        return payload

    return None
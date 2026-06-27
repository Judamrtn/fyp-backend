"""
In-memory token blacklist for logout.
Uses a simple set — good enough for single-server dev.
For production: replace with Redis.
"""
from datetime import datetime, timezone
from typing import Set, Dict
import threading

# Thread-safe blacklist: {token: expires_at_timestamp}
_blacklist: Dict[str, float] = {}
_lock = threading.Lock()


def blacklist_token(token: str, expires_at: float) -> None:
    """Add a token to the blacklist."""
    with _lock:
        _blacklist[token] = expires_at
        _cleanup()


def is_blacklisted(token: str) -> bool:
    """Check if a token is blacklisted."""
    with _lock:
        _cleanup()
        return token in _blacklist


def _cleanup() -> None:
    """Remove expired tokens to prevent memory leak."""
    now = datetime.now(tz=timezone.utc).timestamp()
    expired = [t for t, exp in _blacklist.items() if exp < now]
    for t in expired:
        del _blacklist[t]
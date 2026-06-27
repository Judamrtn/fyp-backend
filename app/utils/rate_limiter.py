"""
Simple in-memory rate limiter for auth endpoints.
Limits by IP address.
For production: replace with Redis-based rate limiting.
"""
from datetime import datetime, timezone
from typing import Dict, List
import threading

# {ip: [timestamp, timestamp, ...]}
_requests: Dict[str, List[float]] = {}
_lock = threading.Lock()


def is_rate_limited(ip: str, max_requests: int = 5,
                    window_seconds: int = 60) -> bool:
    """
    Returns True if IP has exceeded max_requests in window_seconds.
    Default: 5 attempts per minute.
    """
    now = datetime.now(tz=timezone.utc).timestamp()
    window_start = now - window_seconds

    with _lock:
        if ip not in _requests:
            _requests[ip] = []

        # Remove old requests outside window
        _requests[ip] = [t for t in _requests[ip] if t > window_start]

        if len(_requests[ip]) >= max_requests:
            return True

        _requests[ip].append(now)
        return False


def get_remaining(ip: str, max_requests: int = 5,
                  window_seconds: int = 60) -> int:
    """Returns how many requests remain in the current window."""
    now = datetime.now(tz=timezone.utc).timestamp()
    window_start = now - window_seconds

    with _lock:
        if ip not in _requests:
            return max_requests
        recent = [t for t in _requests[ip] if t > window_start]
        return max(0, max_requests - len(recent))
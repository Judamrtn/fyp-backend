"""
Shared response envelope used by every endpoint:
  { "success": bool, "data": any, "message": str, "errors": list[str] }
"""
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = "OK"
    errors: List[str] = []


def ok(data: Any = None, message: str = "OK") -> dict:
    return {"success": True, "data": data, "message": message, "errors": []}


def err(message: str, errors: List[str] | None = None, data: Any = None) -> dict:
    return {"success": False, "data": data, "message": message, "errors": errors or []}

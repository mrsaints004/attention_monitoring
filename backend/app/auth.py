from __future__ import annotations
"""Session-scoped instructor capabilities and student device credentials."""
import hashlib
import hmac
from fastapi import Depends, Header, HTTPException
from app.config import settings


def instructor_token(session_id: str) -> str:
    return hmac.new(settings.AUTH_SECRET.encode(), f"instructor:{session_id}".encode(), hashlib.sha256).hexdigest()


def is_instructor(session_id: str, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(instructor_token(session_id), token)


async def require_instructor(session_id: str, authorization: str | None = Header(None)):
    token = authorization.removeprefix("Bearer ") if authorization else None
    if not is_instructor(session_id, token):
        raise HTTPException(403, "Instructor access required. Open the session in the browser that created it.")

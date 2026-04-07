"""
FastAPI dependency injection.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .security import decode_access_token

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """Dependency: get async DB session."""
    # TODO: wire actual SQLAlchemy session
    # from backend.src.db.session import async_session_maker
    # async with async_session_maker() as session:
    #     yield session
    yield None  # placeholder


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    """
    Dependency: get current authenticated user from JWT.
    Raises 401 if not authenticated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return {"user_id": user_id, **payload}


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any] | None:
    """Dependency: get current user, or None if not authenticated."""
    if credentials is None:
        return None
    return get_current_user(credentials)

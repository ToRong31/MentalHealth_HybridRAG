"""
Auth endpoints — login, register, token refresh.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from backend.src.core.security import (
    create_access_token,
    verify_password,
    hash_password,
)
from backend.src.core.deps import get_current_user

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: str
    email: str


# ── In-memory user store (replace with DB in production) ─────────────────────

_users_db: dict[str, dict] = {}  # email -> {user_id, hashed_password}


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/auth/register", response_model=UserResponse)
async def register(body: UserRegister) -> UserResponse:
    """Register a new user."""
    if body.email in _users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_id = f"user-{len(_users_db) + 1}"
    _users_db[body.email] = {
        "user_id": user_id,
        "hashed_password": hash_password(body.password),
    }
    return UserResponse(user_id=user_id, email=body.email)


@router.post("/auth/login", response_model=Token)
async def login(body: UserLogin) -> Token:
    """Authenticate and return JWT token."""
    user = _users_db.get(body.email)
    if user is None or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token({"sub": user["user_id"], "email": body.email})
    return Token(access_token=access_token)


@router.get("/auth/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user."""
    return UserResponse(
        user_id=current_user["user_id"], email=current_user.get("email", "")
    )

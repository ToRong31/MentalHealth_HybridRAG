"""
Authentication-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional

from .user import UserResponse


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiry


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


class AuthResponse(BaseModel):
    user: UserResponse
    token: TokenResponse
    refresh_token: str = None  # Only returned, not stored in client

"""
Authentication-related Pydantic schemas.
"""
from pydantic import BaseModel
from typing import Optional

from .user import UserResponse


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None


class AuthResponse(BaseModel):
    user: UserResponse
    token: Token

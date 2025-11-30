"""Pydantic schemas."""
from .user import UserBase, UserCreate, UserLogin, UserResponse
from .auth import Token, TokenData, AuthResponse
from .chat import (
    ConversationBase,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    MessageBase,
    MessageCreate,
    MessageResponse,
    ChatRequest,
    ChatResponse,
)

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    # Auth schemas
    "Token",
    "TokenData",
    "AuthResponse",
    # Chat schemas
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "ConversationWithMessages",
    "MessageBase",
    "MessageCreate",
    "MessageResponse",
    "ChatRequest",
    "ChatResponse",
]


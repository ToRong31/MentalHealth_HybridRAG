"""
Chat-related Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone


def ensure_utc(dt: datetime) -> str:
    """Ensure datetime has UTC timezone info before serializing"""
    if dt is None:
        return None
    # If naive datetime, assume it's UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC if not already
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


# ================================
# Conversation Schemas
# ================================

class ConversationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)


class ConversationResponse(ConversationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: ensure_utc
        }


# ================================
# Message Schemas
# ================================

class MessageBase(BaseModel):
    content: str
    sender: str = Field(..., pattern="^(user|bot)$")


class MessageCreate(MessageBase):
    conversation_id: int


class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    is_high_risk: bool
    is_mental_health_related: bool
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: ensure_utc
        }


# ================================
# Chat Schemas
# ================================

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    conversation_title: Optional[str] = None  # For auto-creating conversation


class ChatResponse(BaseModel):
    answer: str
    is_mental_health_related: bool
    is_high_risk: bool
    conversation_id: int
    message_id: int
    # New fields from persistent state workflow
    detected_language: Optional[str] = None  # "vi" or "en"
    detected_disease: Optional[str] = None  # Disease name if diagnosed


class ConversationWithMessages(ConversationResponse):
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

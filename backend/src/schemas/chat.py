"""
Chat-related Pydantic schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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


class ConversationWithMessages(ConversationResponse):
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

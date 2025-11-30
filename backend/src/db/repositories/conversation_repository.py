"""
Conversation repository for database operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func

from src.db.db_models.conversation import Conversation, Message


class ConversationRepository:
    """Repository for Conversation model operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, conversation_id: int, user_id: int) -> Optional[Conversation]:
        """Get conversation by ID for a specific user"""
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all_by_user(self, user_id: int) -> List[Conversation]:
        """Get all conversations for a user"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())
    
    async def create(self, user_id: int, title: str) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(
            user_id=user_id,
            title=title
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation
    
    async def delete(self, conversation: Conversation):
        """Delete a conversation"""
        await self.db.delete(conversation)
        await self.db.flush()
    
    async def get_messages(self, conversation_id: int) -> List[Message]:
        """Get all messages for a conversation"""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def add_message(
        self,
        conversation_id: int,
        content: str,
        sender: str,
        is_high_risk: bool = False,
        is_mental_health_related: bool = True
    ) -> Message:
        """Add a message to a conversation"""
        message = Message(
            conversation_id=conversation_id,
            content=content,
            sender=sender,
            is_high_risk=is_high_risk,
            is_mental_health_related=is_mental_health_related
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)
        return message
    
    async def update_timestamp(self, conversation: Conversation):
        """Update conversation's updated_at timestamp"""
        conversation.updated_at = func.now()
        await self.db.flush()

"""
Conversation management service.
"""
import logging
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.conversation_repository import ConversationRepository
from src.db.db_models.user import User
from src.schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    ConversationWithMessages,
    MessageResponse
)


logger = logging.getLogger(__name__)


class ConversationService:
    """Service for conversation management operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
    
    async def list_conversations(self, current_user: User) -> List[ConversationResponse]:
        """Get all conversations for the current user"""
        conversations = await self.conv_repo.get_all_by_user(current_user.id)
        return [ConversationResponse.model_validate(conv) for conv in conversations]
    
    async def create_conversation(
        self,
        conversation_data: ConversationCreate,
        current_user: User
    ) -> ConversationResponse:
        """Create a new conversation"""
        new_conversation = await self.conv_repo.create(
            user_id=current_user.id,
            title=conversation_data.title
        )
        
        await self.db.commit()
        await self.db.refresh(new_conversation)
        
        return ConversationResponse.model_validate(new_conversation)
    
    async def get_conversation(
        self,
        conversation_id: int,
        current_user: User
    ) -> ConversationWithMessages:
        """Get a conversation with all its messages"""
        conversation = await self.conv_repo.get_by_id(conversation_id, current_user.id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        # Load messages
        messages = await self.conv_repo.get_messages(conversation_id)
        
        return ConversationWithMessages(
            **ConversationResponse.model_validate(conversation).model_dump(),
            messages=[MessageResponse.model_validate(msg) for msg in messages]
        )
    
    async def delete_conversation(
        self,
        conversation_id: int,
        current_user: User
    ):
        """Delete a conversation and all its messages"""
        conversation = await self.conv_repo.get_by_id(conversation_id, current_user.id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        await self.conv_repo.delete(conversation)
        await self.db.commit()

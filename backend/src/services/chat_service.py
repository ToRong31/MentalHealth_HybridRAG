"""
Chat service for processing chat messages with RAG workflow.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.conversation_repository import ConversationRepository
from src.db.db_models.user import User
from src.schemas.chat import ChatRequest, ChatResponse
from src.rag.engine import run_graph


logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
    
    async def process_message(
        self,
        request: ChatRequest,
        current_user: User,
        graph
    ) -> ChatResponse:
        """Process a chat message through the RAG workflow"""
        
        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id=current_user.id,
            conversation_id=request.conversation_id,
            title=request.conversation_title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Save user message
        user_message = await self.conv_repo.add_message(
            conversation_id=conversation.id,
            content=request.message,
            sender="user",
            is_high_risk=False,
            is_mental_health_related=True
        )
        
        logger.info(f"User {current_user.username} sent message in conversation {conversation.id}")
        
        # Run the RAG workflow (async)
        final_state = await run_graph(graph, request.message)
        
        # Save bot response
        bot_message = await self.conv_repo.add_message(
            conversation_id=conversation.id,
            content=final_state.get("answer", "I'm sorry, I couldn't process your request."),
            sender="bot",
            is_high_risk=final_state.get("is_high_risk", False),
            is_mental_health_related=final_state.get("is_mental_health_related", False)
        )
        
        # Update conversation timestamp
        await self.conv_repo.update_timestamp(conversation)
        
        await self.db.commit()
        await self.db.refresh(bot_message)
        
        logger.info(f"Bot responded in conversation {conversation.id}")
        
        return ChatResponse(
            answer=bot_message.content,
            is_mental_health_related=bot_message.is_mental_health_related,
            is_high_risk=bot_message.is_high_risk,
            conversation_id=conversation.id,
            message_id=bot_message.id
        )
    
    async def _get_or_create_conversation(
        self,
        user_id: int,
        conversation_id: Optional[int],
        title: str
    ):
        """Get existing conversation or create new one"""
        if conversation_id:
            # Verify conversation belongs to user
            conversation = await self.conv_repo.get_by_id(conversation_id, user_id)
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            return conversation
        else:
            # Create new conversation
            return await self.conv_repo.create(user_id, title)

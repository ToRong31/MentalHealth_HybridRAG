"""
Chat service for processing chat messages with RAG workflow.
Uses persistent state via PostgreSQL checkpointer.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.conversation_repository import ConversationRepository
from src.db.db_models.user import User
from src.schemas.chat import ChatRequest, ChatResponse
from src.rag.engine import run_rag_workflow  # ← NEW API with persistent state


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
        graph  # ← No longer used, kept for backward compatibility
    ) -> ChatResponse:
        """
        Process a chat message through the RAG workflow with persistent state
        
        State Management:
        - Uses PostgreSQL checkpointer for automatic state persistence
        - conversation.id (UUID) is used as thread_id
        - State (slots, buffer, summary) automatically restored from previous turns
        - No manual buffer/summary management needed
        """
        
        # Get or create conversation
        conversation = await self._get_or_create_conversation(
            user_id=current_user.id,
            conversation_id=request.conversation_id,
            title=request.conversation_title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        
        logger.info(f"Processing message for user {current_user.username}, conversation_id={conversation.id}")
        
        # Save user message to database
        user_message = await self.conv_repo.add_message(
            conversation_id=conversation.id,
            content=request.message,
            sender="user",
            is_high_risk=False,
            is_mental_health_related=True
        )
        
        logger.info(f"User message saved, id={user_message.id}")
        
        # ✅ Run RAG workflow with persistent state (NEW API)
        # State (slots, buffer, summary) automatically managed by checkpointer
        # No need to manually pass conversation_buffer or summary_context
        final_state = await run_rag_workflow(
            conversation_id=str(conversation.id),  # ← Used as thread_id for checkpointer
            user_message=request.message,
            user_id=str(current_user.id)
        )
        
        logger.info(
            f"Workflow completed: detected_language={final_state.get('detected_language')}, "
            f"is_high_risk={final_state.get('is_high_risk')}, "
            f"detected_disease={final_state.get('detected_disease', 'none')}"
        )
        
        # Save bot response to database
        bot_message = await self.conv_repo.add_message(
            conversation_id=conversation.id,
            content=final_state.get("answer", "Xin lỗi, tôi không thể xử lý yêu cầu của bạn."),
            sender="bot",
            is_high_risk=final_state.get("is_high_risk", False),
            is_mental_health_related=final_state.get("is_mental_health_related", False)
        )
        
        # Update conversation timestamp
        await self.conv_repo.update_timestamp(conversation)
        
        await self.db.commit()
        await self.db.refresh(bot_message)
        await self.db.refresh(conversation)  # Refresh to get updated timestamp
        
        logger.info(f"Bot response saved, id={bot_message.id}")
        logger.info(f"Conversation updated_at: {conversation.updated_at}")
        
        return ChatResponse(
            answer=bot_message.content,
            is_mental_health_related=bot_message.is_mental_health_related,
            is_high_risk=bot_message.is_high_risk,
            conversation_id=conversation.id,
            message_id=bot_message.id,
            # ✅ Optional: Include additional metadata from workflow
            detected_language=final_state.get("detected_language"),
            detected_disease=final_state.get("detected_disease"),
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

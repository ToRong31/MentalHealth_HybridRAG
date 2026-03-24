"""
Chat endpoint for mental health chatbot.
Now uses persistent state via PostgreSQL checkpointer.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.db_models.user import User
from src.schemas.chat import ChatRequest, ChatResponse
from src.services.chat_service import ChatService
from src.core.deps import get_current_user


router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

# Global variable to store the graph (kept for backward compatibility, but no longer required)
graph = None


def set_graph(g):
    """
    Set the global graph instance (DEPRECATED - kept for backward compatibility)
    
    Graph is now built internally by run_rag_workflow() with checkpointer,
    so this function is no longer necessary but kept to avoid breaking main.py
    """
    global graph
    graph = g
    logger.info("Graph instance set (note: graph is now built internally with checkpointer)")


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main chat endpoint for the mental health chatbot.
    
    Features:
    - Requires authentication
    - Saves messages to database
    - Uses PostgreSQL checkpointer for persistent state
    - State (slots, buffer, summary) automatically managed across turns
    
    Request body:
    {
        "message": "User message",
        "conversation_id": 123 (optional, creates new if not provided),
        "conversation_title": "Chat title" (optional)
    }
    
    Returns:
    {
        "answer": "Bot response",
        "is_mental_health_related": true,
        "is_high_risk": false,
        "conversation_id": 123,
        "message_id": 456,
        "detected_language": "vi",
        "detected_disease": "depression"
    }
    """
    try:
        chat_service = ChatService(db)
        return await chat_service.process_message(request, current_user, graph)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing your message: {str(e)}"
        )

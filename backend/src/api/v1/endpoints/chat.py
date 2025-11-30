"""
Chat endpoint for mental health chatbot.
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

# Global variable to store the graph (will be injected from main.py)
graph = None


def set_graph(g):
    """Set the global graph instance"""
    global graph
    graph = g


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main chat endpoint for the mental health chatbot.
    Requires authentication and saves messages to database.
    """
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Graph not initialized. Please try again later."
        )
    
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

"""
Health check endpoints.
"""
from fastapi import APIRouter

from src.api.v1.endpoints import chat


router = APIRouter(tags=["Health"])


@router.get("/")
async def root():
    """Root health check endpoint"""
    return {
        "status": "healthy",
        "service": "Mental Health Chatbot API",
        "version": "2.0.0"
    }


@router.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "graph_initialized": chat.graph is not None,
        "database": "connected"
    }

"""
API v1 router aggregator.
"""
from fastapi import APIRouter

from .endpoints import health, auth, conversations, chat


# Create v1 router
api_v1_router = APIRouter(prefix="/api/v1")

# Include all endpoint routers
api_v1_router.include_router(auth.router)
api_v1_router.include_router(conversations.router)
api_v1_router.include_router(chat.router)

# Health checks at root level (not under /api/v1)
health_router = APIRouter()
health_router.include_router(health.router)

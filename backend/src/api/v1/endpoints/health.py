"""
Health check endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe — checks DB and Redis connectivity."""
    # TODO: check DB + Redis
    return {
        "status": "ready",
        "db": "unknown",
        "redis": "unknown",
    }

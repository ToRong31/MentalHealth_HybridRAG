"""
FastAPI Application Factory.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan events — startup and shutdown."""
    logger.info(f"[App] Starting {settings.app_name} ...")
    # Startup: init DB, Redis, AI engine will be lazy-loaded
    yield
    # Shutdown: cleanup
    logger.info("[App] Shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory — wires routers and middleware.
    """
    app = FastAPI(
        title=settings.app_name,
        description="Mental Health Hybrid RAG — Domain-Centric Multi-Agent AI Engine",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ─────────────────────────────────────────────────────────────
    from .api.v1.endpoints import chat, health, auth

    app.include_router(health.router, tags=["Health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
    app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])

    # ── Root ────────────────────────────────────────────────────────────────
    @app.get("/")
    async def root() -> dict[str, str]:
        return {"app": settings.app_name, "status": "running"}

    logger.info(f"[App] Created — debug={settings.debug}")
    return app

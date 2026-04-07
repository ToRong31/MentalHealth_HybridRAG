"""
Application settings — loaded from environment variables.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    # ── App ────────────────────────────────────────────────────────────────
    app_name: str = "Mental Health Hybrid RAG"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # ── Server ──────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database ───────────────────────────────────────────────────────────
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/mental_health",
    )

    # ── Redis ───────────────────────────────────────────────────────────────
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── JWT ────────────────────────────────────────────────────────────────
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── AI Engine ──────────────────────────────────────────────────────────
    ai_max_buffer_size: int = 3
    ai_cache_ttl: int = 3600
    ai_timeout_seconds: int = 60

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # Set LLM_PROVIDER=openai (NVIDIA) or LLM_PROVIDER=gemini
    # OpenAI-compatible (NVIDIA API)
    llm_provider: str = "openai"  # "openai" | "gemini"
    openai_base_url: str = "https://integrate.api.nvidia.com/v1"
    openai_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    # Gemini
    gemini_model: str = "gemini-1.5-flash"

    # ── CORS ───────────────────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

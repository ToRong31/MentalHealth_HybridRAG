"""
Core configuration for the application.
Loads app-wide settings (DB, Secret Key, API, etc.)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from src directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Settings:
    """Application settings configuration class"""
    
    def __init__(self):
        # PostgreSQL Database Configuration
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = os.getenv("DB_PORT", "5432")
        self.DB_NAME = os.getenv("DB_NAME", "mental_health_db")
        self.DB_USER = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")
        
        # Database URL (used by SQLAlchemy)
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        
        # JWT Configuration
        self.SECRET_KEY = os.getenv(
            "SECRET_KEY",
            "Qm2UQ4GvJ8tP3xZ9nL6yA1sD7kF0rV5cH2wM8eR4uT9bN3pC6dJ1lS7vY0zX2"
        )
        self.ALGORITHM = os.getenv("ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1))
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
        # Legacy support
        self.ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))
        
        # Backend API Configuration
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")
        self.API_PORT = int(os.getenv("API_PORT", "8000"))
        
        # PgAdmin Configuration (for Docker)
        self.PGADMIN_EMAIL = os.getenv("PGADMIN_EMAIL", "admin@admin.com")
        self.PGADMIN_PASSWORD = os.getenv("PGADMIN_PASSWORD", "admin123")
        self.PGADMIN_PORT = os.getenv("PGADMIN_PORT", "5050")
        
        # Environment
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# Create global settings instance
settings = Settings()

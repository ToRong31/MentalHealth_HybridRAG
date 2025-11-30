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


# PostgreSQL Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "mental_health_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")

# Database URL (used by SQLAlchemy)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# JWT Configuration
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "Qm2UQ4GvJ8tP3xZ9nL6yA1sD7kF0rV5cH2wM8eR4uT9bN3pC6dJ1lS7vY0zX2"
)
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))

# Backend API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# PgAdmin Configuration (for Docker)
PGADMIN_EMAIL = os.getenv("PGADMIN_EMAIL", "admin@admin.com")
PGADMIN_PASSWORD = os.getenv("PGADMIN_PASSWORD", "admin123")
PGADMIN_PORT = os.getenv("PGADMIN_PORT", "5050")

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

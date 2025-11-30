# import os
# from pathlib import Path
# from dotenv import load_dotenv

# # Load .env from src directory (same directory as this config.py file)
# env_path = Path(__file__).parent / '.env'
# load_dotenv(dotenv_path=env_path)


# # E5
# E5_MODEL_NAME = os.getenv("E5_MODEL_NAME", "intfloat/e5-large-v2")
# E5_DEVICE = os.getenv("E5_DEVICE", "cuda")

# # Milvus / Zilliz
# MILVUS_URI = os.getenv("MILVUS_URI")
# MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
# MILVUS_DB = os.getenv("MILVUS_DB", "default")
# MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "kg_entities")

# # Neo4j
# NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
# NEO4J_USER = os.getenv("NEO4J_USER", "kg_user")
# NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "2005")

# # Gemini
# GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

# # PostgreSQL Database Configuration
# DB_HOST=os.getenv("DB_HOST", "localhost")
# DB_PORT=os.getenv("DB_PORT", "5432")
# DB_NAME=os.getenv("DB_NAME", "mental_health_db")
# DB_USER=os.getenv("DB_USER", "postgres")
# DB_PASSWORD=os.getenv("DB_PASSWORD", "postgres123")

# # Database URL (used by SQLAlchemy)
# DATABASE_URL=os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres123@localhost:5432/mental_health_db")

# # JWT Configuration
# SECRET_KEY=os.getenv("SECRET_KEY", "Qm2UQ4GvJ8tP3xZ9nL6yA1sD7kF0rV5cH2wM8eR4uT9bN3pC6dJ1lS7vY0zX2")
# ALGORITHM=os.getenv("ALGORITHM", "HS256")
# ACCESS_TOKEN_EXPIRE_DAYS=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))

# # Backend API Configuration
# API_HOST=os.getenv("API_HOST", "0.0.0.0")
# API_PORT=os.getenv("API_PORT", "8000")

# # PgAdmin Configuration (for Docker)
# PGADMIN_EMAIL=os.getenv("PGADMIN_EMAIL", "admin@admin.com")
# PGADMIN_PASSWORD=os.getenv("PGADMIN_PASSWORD", "admin123")
# PGADMIN_PORT=os.getenv("PGADMIN_PORT", "5050")

# # Environment
# ENVIRONMENT=os.getenv("ENVIRONMENT", "development")
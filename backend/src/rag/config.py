"""
RAG-specific configuration.
Loads settings for E5, Milvus, Neo4j, and Gemini.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from src directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


# E5 Embedding Model
E5_MODEL_NAME = os.getenv("E5_MODEL_NAME", "intfloat/e5-large-v2")
E5_DEVICE = os.getenv("E5_DEVICE", "cuda")

# Milvus / Zilliz Cloud
MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
MILVUS_DB = os.getenv("MILVUS_DB", "default")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "kg_entities")

# Neo4j Graph Database
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "kg_user")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "2005")

# Google Gemini
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

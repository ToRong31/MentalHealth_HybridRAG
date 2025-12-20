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


class RAGSettings:
    """RAG-specific configuration class for AI components"""
    
    def __init__(self):
        # E5 Embedding Model
        self.E5_MODEL_NAME = os.getenv("E5_MODEL_NAME", "intfloat/e5-large-v2")
        self.E5_DEVICE = os.getenv("E5_DEVICE", "cuda")
        
        # Milvus / Zilliz Cloud
        self.MILVUS_URI = os.getenv("MILVUS_URI")
        self.MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
        self.MILVUS_DB = os.getenv("MILVUS_DB", "default")
        self.MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "kg_entities")
        
        # HNSW Index Parameters
        self.HNSW_M = int(os.getenv("HNSW_M", "16"))
        self.HNSW_EF_CONSTRUCTION = int(os.getenv("HNSW_EF_CONSTRUCTION", "200"))
        self.HNSW_EF = int(os.getenv("HNSW_EF", "128"))
        
        # Neo4j Graph Database
        self.NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.NEO4J_USER = os.getenv("NEO4J_USER", "kg_user")
        self.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "2005")
        
        # Google Gemini
        self.GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")


# Create global RAG settings instance
rag_settings = RAGSettings()


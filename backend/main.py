"""
Mental Health Chatbot API - Main Application
Refactored with clean architecture
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# Core
from src.core.config import API_HOST, API_PORT

# Database
from src.db import init_db, close_db

# RAG
from src.rag import build_kg_graph
from src.rag.vectors.embeddings import e5_model, tokenizer, device

# API Routes
from src.api import api_v1_router, health_router
from src.api.v1.endpoints import chat


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to store the graph
graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the graph, database, and preload E5 model on startup"""
    global graph
    try:
        logger.info("=" * 70)
        logger.info("INITIALIZING APPLICATION")
        logger.info("=" * 70)
        
        # Initialize database
        logger.info("Step 1: Initializing PostgreSQL database...")
        await init_db()
        logger.info("✓ Database initialized")
        
        # Preload E5 model
        logger.info("Step 2: Preloading E5 embedding model...")
        logger.info(f"✓ E5 model loaded on {device.upper()}")
        logger.info(f"  Model will be reused for all requests (no reload)")
        
        # Initialize graph workflow
        logger.info("Step 3: Initializing KG Graph workflow...")
        graph = build_kg_graph()
        # Inject graph into chat endpoint
        chat.set_graph(graph)
        logger.info("✓ KG Graph workflow ready")
        
        logger.info("=" * 70)
        logger.info("✓ APPLICATION READY")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"✗ Failed to initialize: {e}")
        raise
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Mental Health Chatbot API",
    description="RAG-based chatbot for mental health support with user authentication",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:80",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:80",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"[REQUEST] {request.method} {request.url.path}")
    auth_header = request.headers.get("authorization", "NOT SET")
    logger.info(f"[REQUEST] Authorization header: {auth_header[:50] if auth_header != 'NOT SET' else 'NOT SET'}...")
    response = await call_next(request)
    logger.info(f"[RESPONSE] Status: {response.status_code}")
    return response


# Include routers
app.include_router(health_router)
app.include_router(api_v1_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True
    )

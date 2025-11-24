from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
from contextlib import asynccontextmanager

# Import your existing workflow
from src.workflow import build_kg_graph, KGState

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to store the graph
graph = None

from src.vectors.embeddings import e5_model, tokenizer, device
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the graph and preload E5 model on startup"""
    global graph
    try:
        logger.info("=" * 70)
        logger.info("INITIALIZING APPLICATION")
        logger.info("=" * 70)
        
        # Preload E5 model (load once, use forever)
        logger.info("Step 1: Preloading E5 embedding model...")
        from src.vectors.embeddings import e5_model, tokenizer, device
        logger.info(f"✓ E5 model loaded on {device.upper()}")
        logger.info(f"  Model will be reused for all requests (no reload)")
        
        # Initialize graph workflow
        logger.info("Step 2: Initializing KG Graph workflow...")
        graph = build_kg_graph()
        logger.info("✓ KG Graph workflow ready")
        
        logger.info("=" * 70)
        logger.info("✓ APPLICATION READY - Model cached in memory")
        logger.info("=" * 70)
    except Exception as e:
        logger.error(f"✗ Failed to initialize: {e}")
        raise
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Mental Health Chatbot API",
    description="RAG-based chatbot for mental health support",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    is_mental_health_related: bool
    is_high_risk: bool
    session_id: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Mental Health Chatbot API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "graph_initialized": graph is not None
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint for the mental health chatbot
    
    Args:
        request: ChatRequest containing the user's message
        
    Returns:
        ChatResponse with the bot's answer and metadata
    """
    global graph
    
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Graph not initialized. Please try again later."
        )
    
    try:
        logger.info(f"Received message: {request.message}")
        
        # Initialize state for the workflow
        initial_state: KGState = {
            "question": request.message,
            "original_question": "",  
            "user_language": "en",    
            "is_mental_health_related": False,
            "is_high_risk": False,
            "query_embedding": [],
            "anchors": [],
            "nodes": [],
            "rels": [],
            "graph_context": "",
            "dense_context": "",
            "answer": "",
            "done": False,
        }
        
        # Run the workflow
        final_state = graph.invoke(initial_state)
        
        # Log the results
        logger.info(f"Mental health related: {final_state.get('is_mental_health_related')}")
        logger.info(f"High risk: {final_state.get('is_high_risk')}")
        
        # Return the response
        return ChatResponse(
            answer=final_state.get("answer", "I'm sorry, I couldn't process your request."),
            is_mental_health_related=final_state.get("is_mental_health_related", False),
            is_high_risk=final_state.get("is_high_risk", False),
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing your message: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from typing import List
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.sql import func

# Import existing workflow
from src.workflow import build_kg_graph, KGState

# Import database
from src.database import get_db, init_db, close_db

# Import models and schemas
from src.models import User, Conversation, Message
from src.schemas import (
    UserCreate, UserResponse, UserLogin, AuthResponse,
    Token, ChatRequest, ChatResponse,
    ConversationCreate, ConversationResponse, ConversationWithMessages,
    MessageResponse
)
from src.auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, get_user_by_email, get_user_by_username
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to store the graph
graph = None

from src.vectors.embeddings import e5_model, tokenizer, device


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
        from src.vectors.embeddings import e5_model, tokenizer, device
        logger.info(f"✓ E5 model loaded on {device.upper()}")
        logger.info(f"  Model will be reused for all requests (no reload)")
        
        # Initialize graph workflow
        logger.info("Step 3: Initializing KG Graph workflow...")
        graph = build_kg_graph()
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


app = FastAPI(
    title="Mental Health Chatbot API",
    description="RAG-based chatbot for mental health support with user authentication",
    version="2.0.0",
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

# Add request logging middleware for debugging
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"[REQUEST] {request.method} {request.url.path}")
    auth_header = request.headers.get("authorization", "NOT SET")
    logger.info(f"[REQUEST] Authorization header: {auth_header[:50] if auth_header != 'NOT SET' else 'NOT SET'}...")
    response = await call_next(request)
    logger.info(f"[RESPONSE] Status: {response.status_code}")
    return response


# ================================
# Health Check Endpoints
# ================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Mental Health Chatbot API",
        "version": "2.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "graph_initialized": graph is not None,
        "database": "connected"
    }


# ================================
# Authentication Endpoints
# ================================

@app.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user"""
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    existing_username = await get_user_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Create access token (sub must be string per JWT spec)
    access_token = create_access_token(data={"sub": str(new_user.id)})
    
    return AuthResponse(
        user=UserResponse.model_validate(new_user),
        token=Token(access_token=access_token)
    )


@app.post("/auth/login", response_model=AuthResponse)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login user and return access token"""
    user = await authenticate_user(db, user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token (sub must be string per JWT spec)
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=Token(access_token=access_token)
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return UserResponse.model_validate(current_user)


# ================================
# Conversation Endpoints
# ================================

@app.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all conversations for the current user"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    return [ConversationResponse.model_validate(conv) for conv in conversations]


@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation"""
    new_conversation = Conversation(
        user_id=current_user.id,
        title=conversation_data.title
    )
    
    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)
    
    return ConversationResponse.model_validate(new_conversation)


@app.get("/conversations/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a conversation with all its messages"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Load messages
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = messages_result.scalars().all()
    
    return ConversationWithMessages(
        **ConversationResponse.model_validate(conversation).model_dump(),
        messages=[MessageResponse.model_validate(msg) for msg in messages]
    )


@app.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation and all its messages"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    await db.delete(conversation)
    await db.commit()


# ================================
# Chat Endpoint
# ================================

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main chat endpoint for the mental health chatbot.
    Requires authentication and saves messages to database.
    """
    global graph
    
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Graph not initialized. Please try again later."
        )
    
    try:
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            # Verify conversation belongs to user
            result = await db.execute(
                select(Conversation)
                .where(Conversation.id == request.conversation_id, Conversation.user_id == current_user.id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        else:
            # Create new conversation
            title = request.conversation_title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            conversation = Conversation(
                user_id=current_user.id,
                title=title
            )
            db.add(conversation)
            await db.flush()  # Get the ID without committing
        
        # Save user message
        user_message = Message(
            conversation_id=conversation.id,
            content=request.message,
            sender="user",
            is_high_risk=False,
            is_mental_health_related=True
        )
        db.add(user_message)
        await db.flush()
        
        logger.info(f"User {current_user.username} sent message in conversation {conversation.id}")
        
        # Run the workflow
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
        
        final_state = graph.invoke(initial_state)
        
        # Save bot response
        bot_message = Message(
            conversation_id=conversation.id,
            content=final_state.get("answer", "I'm sorry, I couldn't process your request."),
            sender="bot",
            is_high_risk=final_state.get("is_high_risk", False),
            is_mental_health_related=final_state.get("is_mental_health_related", False)
        )
        db.add(bot_message)
        
        # Update conversation timestamp
        conversation.updated_at = func.now()
        
        await db.commit()
        await db.refresh(bot_message)
        
        logger.info(f"Bot responded in conversation {conversation.id}")
        
        return ChatResponse(
            answer=bot_message.content,
            is_mental_health_related=bot_message.is_mental_health_related,
            is_high_risk=bot_message.is_high_risk,
            conversation_id=conversation.id,
            message_id=bot_message.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing your message: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    from datetime import datetime
    from sqlalchemy.sql import func
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

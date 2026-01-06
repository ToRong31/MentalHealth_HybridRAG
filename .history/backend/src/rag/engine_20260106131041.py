"""
RAG engine - Entry point for running the graph workflow with persistent state.

This module provides the main interface for executing the conversational RAG workflow
with PostgreSQL-backed state persistence via LangGraph checkpointer.

Key Features:
- Persistent state across conversation turns
- State survives server restarts (PostgreSQL checkpoint)
- Thread-based isolation (one thread per conversation_id)
- Automatic state save/restore after each node execution

Functions:
- run_rag_workflow: Main entry point for chat service (conversation-based)
- get_conversation_state: Get current state of a conversation
- get_conversation_history: Get full checkpoint history
- run_graph: Legacy function (backward compatibility, NOT recommended)

Migration Guide:
    OLD (deprecated):
    >>> result = await run_graph(graph, question, buffer, summary)
    
    NEW (recommended):
    >>> result = await run_rag_workflow(conversation_id, user_message, user_id)
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List

from .workflow.workflow import build_kg_graph
from .workflow.checkpointer import get_checkpointer


logger = logging.getLogger(__name__)


# ========== NEW: Workflow Execution Functions ==========

async def run_rag_workflow(
    conversation_id: str,
    user_message: str,
    user_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Run RAG workflow với persistent state (RECOMMENDED)
    
    This is the main entry point for executing conversational RAG with full
    state persistence across turns. State is automatically saved to PostgreSQL
    after each node execution and restored on subsequent calls.
    
    State Persistence:
    - All state (slots, buffer, summary, etc.) persists across turns
    - State survives server restarts
    - Each conversation_id maps to a unique thread_id in checkpointer
    - No manual state management needed
    
    Args:
        conversation_id: Unique conversation ID from database
                        Format: UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")
        user_message: User's message/question
        user_id: Optional user ID for tracking
        **kwargs: Additional fields to add to initial state
    
    Returns:
        dict: Final workflow state containing:
            - answer: Generated response
            - detected_language: "vi" or "en"
            - is_high_risk: Boolean risk flag
            - is_mental_health_related: Boolean relevance flag
            - filled_slots: Extracted structured information
            - conversation_buffer: Recent conversation history (last 3 pairs)
            - conversation_summary: Summary of older messages
            - detected_disease: Disease name if diagnosed
            - query_type: "follow_up", "topic_change", or "off_topic"
            - has_sufficient_slots: Boolean indicating if slots are filled
            - ... and other KGState fields
    
    Example:
        >>> # First message in conversation
        >>> result = await run_rag_workflow(
        ...     conversation_id="abc-123-def",
        ...     user_message="Tôi buồn quá",
        ...     user_id="user_001"
        ... )
        >>> print(result["answer"])
        >>> print(result["filled_slots"])  # {"emotion": "buồn", ...}
        
        >>> # Second message (state restored automatically)
        >>> result = await run_rag_workflow(
        ...     conversation_id="abc-123-def",  # Same ID!
        ...     user_message="Tôi ngủ không được nữa"
        ... )
        >>> # filled_slots now includes both turns: {"emotion": "buồn", "sleep": "không được", ...}
    
    Raises:
        Exception: If workflow execution fails
    """
    logger.info(f"[ENGINE] Running RAG workflow for conversation_id={conversation_id}")
    
    # Build graph with checkpointer first
    graph = build_kg_graph()
    
    # Convert conversation_id to thread_id for checkpointer
    thread_id = f"conversation_{conversation_id}"
    
    # Config with thread_id
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }
    
    # Load existing state from checkpoint (if any) to get conversation context
    checkpointer = get_checkpointer()
    existing_state = None
    try:
        checkpoint = checkpointer.get(config)
        if checkpoint and checkpoint.get("channel_values"):
            existing_state = checkpoint["channel_values"]
            logger.info(f"[ENGINE] Loaded existing state from checkpoint with {len(existing_state.get('conversation_buffer', []))} buffer pairs")
    except Exception as e:
        logger.warning(f"[ENGINE] Failed to load existing checkpoint: {e}")
    
    # Classify query with conversation context (if available)
    from src.rag.llm.answer_nodes.query_type_classifier import classify_query_type
    
    conversation_buffer = existing_state.get("conversation_buffer", []) if existing_state else []
    summary_context = existing_state.get("summary_context", "") if existing_state else ""
    
    classifier_result = await classify_query_type(
        question=user_message,
        conversation_buffer=conversation_buffer,
        summary_context=summary_context
    )
    query_type = classifier_result.get("query_type", "follow_up")
    logger.info(f"[ENGINE] Query type detected: {query_type} (with context: {len(conversation_buffer)} buffer pairs)")
    
    # Clear checkpoint if topic_change or off_topic
    if query_type in ["topic_change", "off_topic"]:
        logger.info(f"[ENGINE] {query_type.upper()}: Creating empty checkpoint for fresh start")
        
        # Create empty checkpoint - workflow will start with clean state
        try:
            from langgraph.checkpoint.base import empty_checkpoint
            
            # Create empty checkpoint for this thread
            await checkpointer.aput(
                config,
                empty_checkpoint(),
                {},  # Empty metadata
                {}   # Empty new_versions
            )
            logger.info(f"[ENGINE] Empty checkpoint created for thread_id={thread_id}")
        except Exception as e:
            logger.warning(f"[ENGINE] Failed to create empty checkpoint: {e}")
    
    # Initial state - will be merged with checkpoint (if any)
    initial_state = {
        "question": user_message,
        "conversation_id": conversation_id,
    }
    
    if user_id:
        initial_state["user_id"] = user_id
    
    # Add any additional kwargs
    initial_state.update(kwargs)
    
    logger.info(f"[ENGINE] Config: thread_id={thread_id}")
    logger.info(f"[ENGINE] Initial state keys: {list(initial_state.keys())}")
    
    try:
        # Execute workflow
        # Note: Using ainvoke() with sync PostgresSaver is supported by LangGraph
        # Checkpointer automatically:
        # 1. Loads existing state from PostgreSQL (if thread_id exists)
        # 2. Merges with initial_state
        # 3. Saves state after each node execution
        # 4. State survives server restarts
        result = await graph.ainvoke(initial_state, config)
        
        logger.info(f"[ENGINE] Workflow completed for conversation_id={conversation_id}")
        logger.info(f"[ENGINE] Generated answer length: {len(result.get('answer', ''))}")
        
        return result
        
    except Exception as e:
        logger.error(f"[ENGINE] Error in RAG workflow for conversation_id={conversation_id}: {e}", exc_info=True)
        # Return fallback response
        return {
            "answer": "Xin lỗi, tôi gặp lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại.",
            "is_mental_health_related": False,
            "is_high_risk": False,
            "error": str(e),
        }


async def get_current_conversation_state(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get current state of a conversation from checkpoint
    
    Useful for:
    - Debugging: Inspect current state
    - UI: Display filled slots, conversation history to user
    - Analytics: Track conversation progress
    
    Args:
        conversation_id: Unique conversation ID
    
    Returns:
        dict | None: Current state or None if no checkpoint exists
    
    Example:
        >>> state = await get_current_conversation_state("abc-123")
        >>> if state:
        ...     print("Filled slots:", state.get("filled_slots"))
        ...     print("Buffer:", state.get("conversation_buffer"))
        ...     print("Disease:", state.get("detected_disease"))
    """
    checkpointer = get_checkpointer()
    thread_id = f"conversation_{conversation_id}"
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Get latest checkpoint for this thread
        checkpoint = await checkpointer.aget(config)
        
        if checkpoint:
            logger.info(f"[ENGINE] Found checkpoint for conversation_id={conversation_id}")
            # Return the actual state values
            return checkpoint.get("channel_values", {})
        else:
            logger.info(f"[ENGINE] No checkpoint found for conversation_id={conversation_id}")
            return None
            
    except Exception as e:
        logger.error(f"[ENGINE] Error getting state for conversation_id={conversation_id}: {e}")
        return None


async def get_full_conversation_history(conversation_id: str, limit: int = 10) -> List[dict]:
    """
    Get full checkpoint history of a conversation
    
    Returns all checkpoints (state snapshots after each node) for debugging
    and auditing purposes.
    
    Args:
        conversation_id: Unique conversation ID
        limit: Maximum number of checkpoints to return (default 10)
    
    Returns:
        list: List of checkpoint dicts, each containing:
            - checkpoint_id: Unique checkpoint ID
            - channel_values: State at that point
            - metadata: Node name, timestamp, etc.
    
    Example:
        >>> history = await get_full_conversation_history("abc-123", limit=5)
        >>> for checkpoint in history:
        ...     print(f"Node: {checkpoint['metadata'].get('source')}")
        ...     print(f"State: {checkpoint['channel_values']}")
    """
    checkpointer = get_checkpointer()
    thread_id = f"conversation_{conversation_id}"
    
    config = {"configurable": {"thread_id": thread_id}}
    
    history = []
    try:
        # Iterate through all checkpoints for this thread
        async for checkpoint in checkpointer.alist(config, limit=limit):
            history.append(checkpoint)
        
        logger.info(f"[ENGINE] Found {len(history)} checkpoints for conversation_id={conversation_id}")
        return history
        
    except Exception as e:
        logger.error(f"[ENGINE] Error getting history for conversation_id={conversation_id}: {e}")
        return []


# ========== LEGACY FUNCTION (Backward Compatibility) ==========

async def run_graph(
    graph, 
    question: str,
    conversation_buffer: Optional[List[Dict[str, str]]] = None,
    summary_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the RAG graph workflow with a user question (LEGACY - NOT RECOMMENDED)
    
    ⚠️ DEPRECATION WARNING:
    This function is kept for backward compatibility only. It does NOT use
    persistent state and requires manual buffer/summary management.
    
    Use run_rag_workflow() instead for automatic state persistence.
    
    Args:
        graph: Compiled LangGraph workflow (from build_kg_graph)
        question: User's question
        conversation_buffer: Manual list of previous Q&A pairs [{"user": "...", "bot": "..."}]
        summary_context: Manual summary of older conversation pairs
    
    Returns:
        Final state dictionary with answer and metadata
    
    Migration:
        OLD:
        >>> from .workflow.workflow import build_kg_graph
        >>> graph = build_kg_graph()
        >>> result = await run_graph(graph, "Question?", buffer, summary)
        
        NEW:
        >>> result = await run_rag_workflow(conversation_id, "Question?")
    """
    from .workflow.state import KGState
    
    logger.warning("[ENGINE] run_graph() is deprecated. Use run_rag_workflow() instead.")
    
    initial_state: KGState = {
        "question": question,
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
        # Slot Filling Data
        "slots": None,
        "missing_slots": None,
        "relevant_missing_slots": None,
        "follow_up_questions": None,
        # Timing tracking
        "parallel_start_time": None,
        # Conversation Memory (manual management)
        "conversation_buffer": conversation_buffer or [],
        "summary_context": summary_context or "",
        "previous_follow_up_questions": None,
        # Query Classification
        "query_type": None,
        "should_enhance_query": None,
        "query_similarity": None,
        "is_topic_change": None,
        "is_off_topic": None,
    }
    
    try:
        # Use ainvoke WITHOUT config (no checkpointer)
        # State will NOT persist across calls
        final_state = await graph.ainvoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"[ENGINE] Error running RAG graph: {e}", exc_info=True)
        return {
            "answer": "I'm sorry, I encountered an error processing your request.",
            "is_mental_health_related": False,
            "is_high_risk": False,
        }

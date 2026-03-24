"""
Query Classifier Node
Node wrapper for query classification logic
"""
from typing import Dict, Any
import logging

from src.rag.llm.answer_nodes.query_type_classifier import classify_query_type

logger = logging.getLogger(__name__)


async def query_type_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Classify query type (follow_up, topic_change, off_topic) using LLM.
    
    Business logic:
    - off_topic: Return polite rejection, END workflow, don't load checkpoint (fresh state)
    - topic_change: Don't load checkpoint (fresh state), continue to other nodes
    - follow_up: Load checkpoint (continue conversation), continue to other nodes
    
    Args:
        state: State dict with question, conversation_buffer, summary_context
    
    Returns:
        Updated state with query_type, is_topic_change, is_off_topic, should_enhance_query,
        skip_checkpoint_load, should_end_workflow
    """
    question = state.get("question", "")
    buffer = state.get("conversation_buffer")
    summary = state.get("summary_context")
    
    # Normalize None to empty values
    if buffer is None:
        buffer = []
    if summary is None:
        summary = ""
    
    # CRITICAL FIX: If buffer/summary are empty, try to reload from checkpoint
    # This handles the case where LangGraph merge didn't work correctly
    if not buffer and not summary:
        logger.warning(f"[CLASSIFY_NODE] ⚠️ Buffer and summary are both empty! Trying to reload from checkpoint...")
        try:
            from src.rag.workflow.checkpointer import get_checkpointer
            checkpointer = get_checkpointer()
            conversation_id = state.get("conversation_id")
            if conversation_id:
                thread_id = f"conversation_{conversation_id}"
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = await checkpointer.aget(config)
                if checkpoint and checkpoint.get("channel_values"):
                    checkpoint_state = checkpoint["channel_values"]
                    buffer = checkpoint_state.get("conversation_buffer")
                    summary = checkpoint_state.get("summary_context")
                    # Normalize again
                    if buffer is None:
                        buffer = []
                    if summary is None:
                        summary = ""
                    logger.info(f"[CLASSIFY_NODE] ✓ Reloaded from checkpoint: buffer={len(buffer)} pairs, summary={'yes' if summary else 'no'}")
        except Exception as e:
            logger.error(f"[CLASSIFY_NODE] Error reloading checkpoint: {e}")
    
    # If absolutely no context is present after reload, force first turn to topic_change
    if not buffer and not summary:
        logger.info("[CLASSIFY_NODE] No previous context after reload -> force query_type=topic_change")
        result = {
            "query_type": "topic_change",
            "is_topic_change": True,
            "is_off_topic": False,
            "should_enhance_query": True,
        }
    else:
        # Debug logging to check if buffer/summary are loaded from checkpoint
        logger.info(f"[CLASSIFY_NODE] ===== CLASSIFICATION DEBUG =====")
        logger.info(f"[CLASSIFY_NODE] Question: {question[:100]}...")
        logger.info(f"[CLASSIFY_NODE] Buffer: {len(buffer)} pairs (type: {type(buffer).__name__})")
        logger.info(f"[CLASSIFY_NODE] Summary: {'yes' if summary else 'no'} (type: {type(summary).__name__}, length: {len(summary) if summary else 0})")
        if buffer:
            logger.info(f"[CLASSIFY_NODE] Buffer content: {buffer}")
        if summary:
            logger.info(f"[CLASSIFY_NODE] Summary preview: {summary[:200]}...")
        logger.info(f"[CLASSIFY_NODE] Will call classify_query_type with buffer={len(buffer)}, summary={'yes' if summary else 'no'}")
        
        # Call logic function
        result = await classify_query_type(
            question=question,
            conversation_buffer=buffer,
            summary_context=summary
        )
        
        logger.info(f"[CLASSIFY_NODE] Classification result: {result.get('query_type')} (is_topic_change={result.get('is_topic_change')})")
        logger.info(f"[CLASSIFY_NODE] ===== END CLASSIFICATION DEBUG =====")
    
    # Update state with result
    state.update(result)
    
    query_type = result.get("query_type", "follow_up")
    
    # Handle off_topic: reject politely and END workflow
    if query_type == "off_topic":
        logger.info("Query classified as OFF_TOPIC - end workflow with rejection")
        
        # Set polite rejection message
        state["answer"] = (
            "Xin lỗi, tôi là trợ lý tư vấn sức khỏe tâm thần. "
            "Câu hỏi của bạn có vẻ nằm ngoài chuyên môn của tôi. "
            "Tôi chỉ có thể hỗ trợ các vấn đề liên quan đến sức khỏe tâm thần, "
            "cảm xúc, stress, lo âu, trầm cảm và các khó khăn tâm lý khác. "
            "Bạn có thể đặt câu hỏi khác về sức khỏe tâm thần không?"
        )
        
        # Set flags (checkpoint already cleared by engine)
        state["is_mental_health_related"] = False
        state["should_end_workflow"] = True
        
        logger.info("OFF_TOPIC: Workflow will end, checkpoint already cleared by engine")
    
    # Handle topic_change: continue processing with fresh state
    elif query_type == "topic_change":
        logger.info("Query classified as TOPIC_CHANGE - continue with fresh state")
        
        # Set flag (checkpoint already cleared by engine, so state is fresh)
        state["should_end_workflow"] = False
        
        logger.info("TOPIC_CHANGE: Continue workflow, checkpoint already cleared by engine")
    
    # Handle follow_up: continue conversation normally with existing state
    else:  # follow_up
        logger.info("Query classified as FOLLOW_UP - continue with existing state")
        
        state["should_end_workflow"] = False
        
        logger.info("FOLLOW_UP: Continue with checkpoint state")
    
    return state

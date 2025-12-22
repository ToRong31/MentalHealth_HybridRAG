"""
Query Rewriter
Rewrite user query with filled slots and conversation memory for better retrieval
"""
import asyncio
import logging
from typing import Dict, Any, List

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt
from src.rag.utils.memory import format_buffer_for_context, format_summary_context

logger = logging.getLogger(__name__)

# Load rewriter prompt from YAML
try:
    rewriter_prompts = load_prompts("rewritter_promt.yaml")
    QUERY_REWRITE_TEMPLATE = rewriter_prompts.get("query_rewrite_prompt", "")
    if not QUERY_REWRITE_TEMPLATE:
        raise ValueError("query_rewrite_prompt not found in rewritter_promt.yaml")
    logger.info("Successfully loaded query rewrite prompt from YAML")
except Exception as e:
    logger.error(f"Failed to load rewriter prompt: {e}")
    QUERY_REWRITE_TEMPLATE = ""


async def rewrite_query_with_slots(
    original_question: str,
    slots: Dict[str, Any],
    conversation_buffer: List[Dict[str, str]] = None,
    summary_context: str = ""
) -> str:
    """
    Rewrite user query using filled slots and conversation memory for better retrieval.
    
    Args:
        original_question: User's original question
        slots: Filled slots from slot filling
        conversation_buffer: Recent conversation history
        summary_context: Summary of older conversation
    
    Returns:
        Rewritten query string
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    try:
        from src.rag.utils.slots import build_query_context_from_slots
        
        # Build context from slots
        slot_context = build_query_context_from_slots(slots)
        
        if not slot_context and not conversation_buffer and not summary_context:
            logger.info("No context available (slots, buffer, or summary), using original query")
            return original_question
        
        # Format conversation memory (use only last 3 pairs)
        recent_buffer = conversation_buffer[-3:] if conversation_buffer else []
        buffer_text = format_buffer_for_context(recent_buffer) if recent_buffer else "No recent conversation"
        summary_text = format_summary_context(summary_context) if summary_context else "No previous summary"
        
        # Build prompt using template from YAML
        if not QUERY_REWRITE_TEMPLATE:
            logger.warning("Rewrite template not loaded, using original query")
            return original_question
        
        prompt = format_prompt(
            QUERY_REWRITE_TEMPLATE,
            ORIGINAL_QUESTION=original_question,
            SLOT_CONTEXT=slot_context or "No structured context extracted",
            CONVERSATION_BUFFER=buffer_text,
            CONVERSATION_SUMMARY=summary_text
        )
        
        # ========== BEGIN: QUERY REWRITE DEBUG LOG (Remove when done) ==========
        logger.info("="*80)
        logger.info("QUERY REWRITING")
        logger.info("="*80)
        logger.info(f"📝 Original: {original_question}")
        logger.info(f"🎯 Slot context: {slot_context or 'None'}")
        if conversation_buffer:
            logger.info(f"💬 Buffer: Using last 3 of {len(conversation_buffer)} messages")
        if summary_context:
            logger.info(f"📋 Summary: {summary_context[:100]}...")
        # ========== END: QUERY REWRITE DEBUG LOG ==========
        
        # Call LLM to rewrite
        loop = asyncio.get_event_loop()
        rewritten = await loop.run_in_executor(
            None, 
            lambda: llm.invoke(prompt, max_retries=2)
        )
        
        rewritten = rewritten.strip()
        
        # Fallback to original if rewrite seems invalid
        if not rewritten or len(rewritten) < 5:
            logger.warning("Rewritten query too short, using original")
            return original_question
        
        logger.info(f"✅ Rewritten: {rewritten}")
        logger.info("="*80)
        
        return rewritten
        
    except Exception as e:
        logger.error(f"Error rewriting query: {e}", exc_info=True)
        return original_question

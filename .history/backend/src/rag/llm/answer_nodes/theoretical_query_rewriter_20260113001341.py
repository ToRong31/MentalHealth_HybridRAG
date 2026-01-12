"""
Theoretical Query Rewriter
Rewrite theoretical mental health questions for optimized retrieval
"""
import asyncio
import logging
from typing import Dict, Any, List

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt
from src.rag.utils.memory import format_buffer_for_context, format_summary_context

logger = logging.getLogger(__name__)

# Load theoretical rewriter prompt from YAML
try:
    theoretical_prompts = load_prompts("theoretical_rewriter_prompt.yaml")
    THEORETICAL_REWRITE_TEMPLATE = theoretical_prompts.get("theoretical_query_rewrite_prompt", "")
    if not THEORETICAL_REWRITE_TEMPLATE:
        raise ValueError("theoretical_query_rewrite_prompt not found in theoretical_rewriter_prompt.yaml")
    logger.info(f"✅ Successfully loaded theoretical query rewrite prompt (length: {len(THEORETICAL_REWRITE_TEMPLATE)} chars)")
except Exception as e:
    logger.error(f"❌ Failed to load theoretical rewriter prompt: {e}")
    THEORETICAL_REWRITE_TEMPLATE = ""


async def rewrite_theoretical_query(
    original_question: str,
    conversation_buffer: List[Dict[str, str]] = None,
    summary_context: str = ""
) -> str:
    """
    Rewrite theoretical question for better retrieval.
    
    Handles:
    - Definition questions (là gì, what is)
    - Symptom questions (triệu chứng)
    - Causes questions (nguyên nhân)
    - Treatment questions (điều trị)
    - Comparison questions (khác nhau)
    - Diagnostic criteria questions (chẩn đoán)
    
    Features:
    - Vietnamese to English translation
    - Clinical terminology expansion
    - Coreference resolution (using conversation context)
    - Question-type specific keywords
    
    Args:
        original_question: User's theoretical question
        conversation_buffer: Recent conversation history
        summary_context: Summary of older conversation
    
    Returns:
        Rewritten query string in English with keywords
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    try:
        # Format conversation memory
        recent_buffer = conversation_buffer[-3:] if conversation_buffer else []
        buffer_text = format_buffer_for_context(recent_buffer) if recent_buffer else "No recent conversation"
        summary_text = format_summary_context(summary_context) if summary_context else "No previous summary"
        
        # Build prompt using template from YAML
        if not THEORETICAL_REWRITE_TEMPLATE:
            logger.warning("⚠️ Theoretical rewrite template not loaded, using original query")
            return original_question
        
        prompt = format_prompt(
            THEORETICAL_REWRITE_TEMPLATE,
            ORIGINAL_QUESTION=original_question,
            CONVERSATION_BUFFER=buffer_text,
            CONVERSATION_SUMMARY=summary_text
        )
        
        # ========== BEGIN: THEORETICAL QUERY REWRITE DEBUG LOG ==========
        logger.info("="*80)
        logger.info("THEORETICAL QUERY REWRITING")
        logger.info("="*80)
        logger.info(f"📝 Original Question: {original_question}")
        if conversation_buffer:
            logger.info(f"💬 Using conversation context: {len(conversation_buffer)} messages")
            # Log last topic for coreference
            if conversation_buffer:
                last_qa = conversation_buffer[-1]
                logger.info(f"   Last Q: {last_qa.get('question', '')[:50]}...")
        if summary_context:
            logger.info(f"📋 Summary context: {summary_context[:100]}...")
        # ========== END: THEORETICAL QUERY REWRITE DEBUG LOG ==========
        
        # Call LLM to rewrite
        loop = asyncio.get_event_loop()
        rewritten = await loop.run_in_executor(
            None, 
            lambda: llm.invoke(prompt, max_retries=2)
        )
        
        rewritten = rewritten.strip()
        
        # Validation: ensure output is not empty and in English
        if not rewritten or len(rewritten) < 10:
            logger.warning("⚠️ Rewritten query too short, using original")
            return original_question
        
        # Check if rewrite failed (returned Vietnamese)
        if contains_vietnamese(rewritten):
            logger.warning("⚠️ Rewritten query contains Vietnamese, may need better translation")
        
        logger.info(f"✅ Rewritten Query: {rewritten}")
        logger.info("="*80)
        
        return rewritten
        
    except Exception as e:
        logger.error(f"❌ Error rewriting theoretical query: {e}", exc_info=True)
        return original_question


def contains_vietnamese(text: str) -> bool:
    """
    Quick check if text contains Vietnamese characters.
    """
    vietnamese_chars = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ")
    return any(char.lower() in vietnamese_chars for char in text)


def extract_last_topic(conversation_buffer: List[Dict[str, str]]) -> str:
    """
    Extract the main disorder/topic from last conversation turn.
    Used for coreference resolution.
    
    Returns:
        Disorder name or empty string
    """
    if not conversation_buffer:
        return ""
    
    # Get last question
    last_turn = conversation_buffer[-1]
    last_question = last_turn.get("question", "").lower()
    
    # Common disorder keywords
    disorder_keywords = {
        "trầm cảm": "depression",
        "lo âu": "anxiety",
        "ocd": "OCD",
        "ám ảnh": "obsessive-compulsive disorder",
        "ptsd": "PTSD",
        "căng thẳng": "stress",
        "bipolar": "bipolar disorder",
        "lưỡng cực": "bipolar disorder",
        "tâm thần": "schizophrenia",
        "adhd": "ADHD",
        "tự kỷ": "autism",
    }
    
    for vn_term, en_term in disorder_keywords.items():
        if vn_term in last_question:
            return en_term
    
    return ""

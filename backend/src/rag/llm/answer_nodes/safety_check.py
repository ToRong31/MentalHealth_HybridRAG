"""
Safety Check Node
Kiểm tra xem câu hỏi có liên quan đến mental health và có phải high-risk không
Conditional enhancement: enhance query nếu follow_up/topic_change, không enhance nếu off_topic
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts
from src.rag.utils.memory import build_enhanced_query

logger = logging.getLogger(__name__)

# Load safety check prompt
safety_check_prompt_data = load_prompts("safety_check_prompt.yaml")
safety_check_prompt = safety_check_prompt_data.get("safety_check_prompt", "")

if not safety_check_prompt:
    raise ValueError("Safety check prompt is empty! Check safety_check_prompt.yaml file.")


async def process_safety_check(
    question: str,
    query_type: str = None,
    should_enhance: bool = False,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> Dict[str, bool]:
    """
    Process safety check logic: check if question indicates high-risk situation.
    
    Args:
        question: User question
        query_type: Type of query (follow_up, topic_change, off_topic)
        should_enhance: Whether to enhance query with context
        conversation_buffer: Conversation history buffer
        summary_context: Summary of conversation
    
    Returns:
        Dict with is_high_risk flag
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    # Conditional query enhancement
    if should_enhance and query_type in ["follow_up", "topic_change"]:
        enhanced_q = build_enhanced_query(question, conversation_buffer, summary_context)
        q = enhanced_q
        logger.info(f"Enhanced query for safety check (type: {query_type})")
        logger.debug(f"Enhanced query: {enhanced_q[:100]}...")
    else:
        q = question
        if query_type == "off_topic":
            logger.info("Using original query for safety check (off_topic)")
        else:
            logger.info("Using original query for safety check (no enhancement needed)")
    
    # Validate prompt
    if not safety_check_prompt:
        logger.error("Safety check prompt is empty!")
        raise ValueError("Safety check prompt is not loaded properly")
    
    # Create prompt
    prompt = safety_check_prompt.replace("{{QUESTION}}", q)
    logger.info(f"Safety check prompt length: {len(prompt)}")
    
    # Call LLM
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        
        # Parse JSON response
        json_match = re.search(
            r'\{[^{}]*"is_high_risk"[^{}]*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            return {
                "is_high_risk": result.get("is_high_risk", False)
            }
        else:
            logger.warning(f"Could not parse JSON from LLM response: {response}")
            return {
                "is_high_risk": False
            }
            
    except Exception as e:
        logger.error(f"Error in process_safety_check: {e}", exc_info=True)
        return {
            "is_high_risk": False
        }

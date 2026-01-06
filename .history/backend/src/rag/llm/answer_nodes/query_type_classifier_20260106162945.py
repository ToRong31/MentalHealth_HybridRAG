"""
Query Classifier Node
Classify query type: follow_up, topic_change, or off_topic using LLM.
Only runs when similarity < 0.8 (uncertain cases).
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt

logger = logging.getLogger(__name__)

# Query classifier prompt template will be loaded lazily in the async function
query_classifier_prompt_template = None


async def classify_query_type(
    question: str,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> Dict[str, Any]:
    """
    Classify query type using LLM: follow_up, topic_change, or off_topic.
    
    Args:
        question: User question
        conversation_buffer: Conversation history buffer
        summary_context: Summary of conversation
    
    Returns:
        Dict with query_type, is_topic_change, is_off_topic, should_enhance_query
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    # Lazy load prompt template if not loaded yet
    global query_classifier_prompt_template
    if query_classifier_prompt_template is None:
        try:
            query_classifier_prompt_data = await load_prompts("query_classifier_prompt.yaml")
            query_classifier_prompt_template = query_classifier_prompt_data.get("query_classifier_prompt", "")
        except Exception as e:
            logger.error(f"Failed to load query classifier prompt: {e}")
            query_classifier_prompt_template = ""
    
    # Build conversation context from buffer + summary
    from src.rag.utils.memory import format_buffer_for_context, format_summary_context
    
    buffer_text = format_buffer_for_context(conversation_buffer)
    summary_text = format_summary_context(summary_context)
    
    conversation_context_parts = []
    if summary_text:
        conversation_context_parts.append(f"Summary of previous conversation:\n{summary_text}")
    if buffer_text:
        conversation_context_parts.append(f"Recent conversation:\n{buffer_text}")
    
    conversation_context = "\n\n".join(conversation_context_parts) if conversation_context_parts else "No previous conversation."
    
    # Validate prompt
    if not query_classifier_prompt_template:
        logger.error("Query classifier prompt is empty!")
        return {
            "query_type": "follow_up",
            "is_topic_change": False,
            "is_off_topic": False,
            "should_enhance_query": True
        }
    
    # Format prompt
    prompt = format_prompt(
        query_classifier_prompt_template,
        QUESTION=question,
        CONVERSATION_CONTEXT=conversation_context
    )
    
    logger.info(f"Query classifier prompt length: {len(prompt)}")
    logger.debug(f"Classifying query: {question[:50]}...")
    
    # Call LLM
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        # Parse JSON response
        json_match = re.search(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            query_type = result.get("query_type", "follow_up")
            reason = result.get("reason", "")
            
            logger.info(f"Query classified as: {query_type} - {reason}")
            
            is_topic_change = (query_type == "topic_change")
            is_off_topic = (query_type == "off_topic")
            should_enhance_query = (query_type in ["follow_up", "topic_change"])
            
            return {
                "query_type": query_type,
                "is_topic_change": is_topic_change,
                "is_off_topic": is_off_topic,
                "should_enhance_query": should_enhance_query
            }
        else:
            logger.warning(f"Could not parse JSON from LLM response: {response}")
            return {
                "query_type": "follow_up",
                "is_topic_change": False,
                "is_off_topic": False,
                "should_enhance_query": True
            }
            
    except Exception as e:
        logger.error(f"Error in classify_query_type: {e}", exc_info=True)
        return {
            "query_type": "follow_up",
            "is_topic_change": False,
            "is_off_topic": False,
            "should_enhance_query": True
        }


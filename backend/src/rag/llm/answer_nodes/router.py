"""
Personal/Theoretical Classifier
Classify query nature: personal (about user's own situation) or theoretical (general knowledge)
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt

logger = logging.getLogger(__name__)

# Load personal/theoretical classifier prompt
try:
    classifier_prompt_data = load_prompts("personal_theoretical_classifier_prompt.yaml")
    classifier_prompt_template = classifier_prompt_data.get("personal_theoretical_classifier_prompt", "")
except Exception as e:
    logger.error(f"Failed to load personal/theoretical classifier prompt: {e}")
    classifier_prompt_template = ""


async def classify_personal_theoretical(
    question: str,
    query_type: str,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> Dict[str, Any]:
    """
    Classify query nature: personal or theoretical.
    
    Args:
        question: User question
        query_type: Type from query_classifier (follow_up, topic_change, off_topic)
        conversation_buffer: Conversation history buffer
        summary_context: Summary of conversation
    
    Returns:
        Dict with query_nature, reasoning
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
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
    if not classifier_prompt_template:
        logger.error("Personal/theoretical classifier prompt is empty!")
        # Default to personal (safer to gather more info)
        return {
            "query_nature": "personal",
            "reasoning": "Default to personal due to missing prompt"
        }
    
    # Format prompt
    prompt = format_prompt(
        classifier_prompt_template,
        QUESTION=question,
        QUERY_TYPE=query_type,
        CONVERSATION_CONTEXT=conversation_context
    )
    
    logger.info(f"Personal/theoretical classifier prompt length: {len(prompt)}")
    logger.debug(f"Classifying query nature: {question[:50]}...")
    
    # Call LLM
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        # Parse JSON response
        json_match = re.search(
            r'\{[^{}]*"query_nature"[^{}]*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            query_nature = result.get("query_nature", "personal")
            reasoning = result.get("reasoning", "")
            
            # Validate query_nature
            if query_nature not in ["personal", "theoretical"]:
                logger.warning(f"Invalid query_nature '{query_nature}', defaulting to 'personal'")
                query_nature = "personal"
            
            logger.info(f"Query nature classified as: {query_nature} - {reasoning}")
            
            return {
                "query_nature": query_nature,
                "reasoning": reasoning
            }
        else:
            logger.warning(f"Could not parse JSON from LLM response: {response}")
            # Default to personal (safer)
            return {
                "query_nature": "personal",
                "reasoning": "Could not parse LLM response, defaulting to personal"
            }
            
    except Exception as e:
        logger.error(f"Error in classify_personal_theoretical: {e}", exc_info=True)
        # Default to personal (safer)
        return {
            "query_nature": "personal",
            "reasoning": f"Error occurred: {str(e)}, defaulting to personal"
        }

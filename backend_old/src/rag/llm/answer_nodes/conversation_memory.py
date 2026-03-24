"""
Conversation Memory Node
Update conversation buffer and summary context.
Handle topic change, buffer rotation, and summarization.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt
from src.rag.utils.memory import (
    format_message_pair,
    format_buffer_for_context,
    add_pair_to_buffer
)

logger = logging.getLogger(__name__)

# Load summarization prompts
try:
    summarize_prompt_data = load_prompts("conversation_summarize_prompt.yaml")
    summarize_pair_prompt_template = summarize_prompt_data.get("summarize_pair_prompt", "")
    summarize_buffer_prompt_template = summarize_prompt_data.get("summarize_buffer_prompt", "")
except Exception as e:
    logger.error(f"Failed to load summarization prompts: {e}")
    summarize_pair_prompt_template = ""
    summarize_buffer_prompt_template = ""

# Buffer size (max number of Q&A pairs in buffer)
BUFFER_SIZE = 3


async def summarize_pair(pair: Dict[str, str]) -> str:
    """
    Summarize a single Q&A pair using LLM.
    
    Args:
        pair: Q&A pair {"user": "...", "bot": "..."}
    
    Returns:
        Summary string
    """
    if not summarize_pair_prompt_template:
        logger.warning("Summarize pair prompt not available, returning empty summary")
        return ""
    
    try:
        # Format prompt with user and assistant messages
        prompt = format_prompt(
            summarize_pair_prompt_template,
            USER_MESSAGE=pair.get("user", ""),
            ASSISTANT_MESSAGE=pair.get("bot", "")
        )
        
        # Call LLM (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None,
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        # Clean up summary (remove extra whitespace)
        summary = summary.strip()
        
        logger.debug(f"Summarized pair: {summary[:50]}...")
        return summary
        
    except Exception as e:
        logger.error(f"Error summarizing pair: {e}", exc_info=True)
        return ""


async def summarize_buffer(buffer: List[Dict[str, str]]) -> str:
    """
    Summarize entire conversation buffer using LLM.
    
    Args:
        buffer: List of Q&A pairs [{"user": "...", "bot": "..."}]
    
    Returns:
        Summary string
    """
    if not buffer:
        return ""
    
    if not summarize_buffer_prompt_template:
        logger.warning("Summarize buffer prompt not available, returning empty summary")
        return ""
    
    try:
        # Format buffer for prompt
        buffer_text = format_buffer_for_context(buffer)
        
        # Format prompt with buffer
        prompt = format_prompt(
            summarize_buffer_prompt_template,
            CONVERSATION_BUFFER=buffer_text
        )
        
        # Call LLM (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None,
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        # Clean up summary (remove extra whitespace)
        summary = summary.strip()
        
        logger.debug(f"Summarized buffer ({len(buffer)} pairs): {summary[:50]}...")
        return summary
        
    except Exception as e:
        logger.error(f"Error summarizing buffer: {e}", exc_info=True)
        return ""


def combine_summaries(existing_summary: str, new_summary: str) -> str:
    """
    Combine existing summary with new summary.
    
    Args:
        existing_summary: Existing summary text
        new_summary: New summary to add
    
    Returns:
        Combined summary
    """
    if not existing_summary:
        return new_summary
    
    if not new_summary:
        return existing_summary
    
    # Combine summaries with separator
    return f"{existing_summary}\n\n{new_summary}"


async def update_conversation_memory(
    query_type: str,
    question: str,
    answer: str,
    current_buffer: list = None,
    current_summary: str = ""
) -> Dict[str, Any]:
    """
    Update conversation buffer and summary context based on query type.
    
    Logic:
    - off_topic: don't add to buffer
    - topic_change: summarize old buffer, clear, start new topic
    - follow_up: add to buffer, summarize if full
    
    Args:
        query_type: Type of query (follow_up, topic_change, off_topic)
        question: User question
        answer: Bot answer
        current_buffer: Current conversation buffer
        current_summary: Current summary context
    
    Returns:
        Dict with conversation_buffer and summary_context
    """
    if current_buffer is None:
        current_buffer = []
    
    # If off_topic, don't add to buffer
    if query_type == "off_topic":
        logger.info("Off-topic query, not adding to conversation buffer")
        return {
            "conversation_buffer": current_buffer,
            "summary_context": current_summary
        }
    
    # Create current Q&A pair
    current_pair = format_message_pair(question, answer)
    
    # Handle topic change: summarize old buffer, clear, start new topic
    if query_type == "topic_change":
        logger.info("Topic change detected, summarizing old buffer and starting new topic")
        
        if current_buffer:
            old_buffer_summary = await summarize_buffer(current_buffer)
            if old_buffer_summary:
                current_summary = combine_summaries(current_summary, old_buffer_summary)
                logger.info(f"Added old buffer summary to summary context")
        
        new_buffer = [current_pair]
        logger.info(f"Cleared buffer and added new pair (topic change)")
        
        return {
            "conversation_buffer": new_buffer,
            "summary_context": current_summary
        }
    
    # Handle follow_up: add to buffer, summarize if full
    if query_type == "follow_up" or query_type is None:
        logger.info(f"Follow-up query, adding to buffer")
        
        new_buffer, popped_pair = add_pair_to_buffer(current_buffer, current_pair, BUFFER_SIZE)
        
        if popped_pair:
            logger.info(f"Buffer full, summarizing popped pair")
            popped_summary = await summarize_pair(popped_pair)
            if popped_summary:
                current_summary = combine_summaries(current_summary, popped_summary)
                logger.info(f"Added popped pair summary to summary context")
        
        return {
            "conversation_buffer": new_buffer,
            "summary_context": current_summary
        }
    
    # Fallback
    logger.warning(f"Unknown query_type: {query_type}, adding to buffer anyway")
    new_buffer, popped_pair = add_pair_to_buffer(current_buffer, current_pair, BUFFER_SIZE)
    if popped_pair:
        popped_summary = await summarize_pair(popped_pair)
        if popped_summary:
            current_summary = combine_summaries(current_summary, popped_summary)
    
    return {
        "conversation_buffer": new_buffer,
        "summary_context": current_summary
    }


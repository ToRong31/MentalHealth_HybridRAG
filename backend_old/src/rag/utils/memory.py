"""
Conversation Memory Utilities
Helper functions for managing conversation buffer and summary context.
NO LLM calls in this module - only data formatting and management.
"""
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def format_message_pair(user_msg: str, bot_msg: str) -> Dict[str, str]:
    """
    Format a user message and bot response into a Q&A pair.
    
    Args:
        user_msg: User's message
        bot_msg: Bot's response
    
    Returns:
        Dictionary with 'user' and 'bot' keys
    """
    return {
        "user": user_msg,
        "bot": bot_msg
    }


def format_buffer_for_context(buffer: List[Dict[str, str]]) -> str:
    """
    Format conversation buffer into a readable context string.
    
    Args:
        buffer: List of Q&A pairs [{"user": "...", "bot": "..."}]
    
    Returns:
        Formatted string for prompt context
    """
    if not buffer:
        return ""
    
    lines = []
    for i, pair in enumerate(buffer, 1):
        lines.append(f"Exchange {i}:")
        lines.append(f"User: {pair.get('user', '')}")
        lines.append(f"Assistant: {pair.get('bot', '')}")
        lines.append("")  # Empty line between pairs
    
    return "\n".join(lines).strip()


def format_summary_context(summary: str) -> str:
    """
    Format summary context for prompt.
    
    Args:
        summary: Summary text of older conversation
    
    Returns:
        Formatted summary string
    """
    if not summary:
        return ""
    
    return summary.strip()


def get_conversation_pairs(messages: List) -> List[Dict[str, str]]:
    """
    Convert list of Message objects into Q&A pairs.
    
    Args:
        messages: List of Message objects from database
    
    Returns:
        List of Q&A pairs [{"user": "...", "bot": "..."}]
    """
    pairs = []
    current_user_msg = None
    
    for msg in messages:
        if msg.sender == "user":
            current_user_msg = msg.content
        elif msg.sender == "bot" and current_user_msg is not None:
            # Found a pair
            pairs.append(format_message_pair(current_user_msg, msg.content))
            current_user_msg = None
    
    # If last message is user message without bot response, ignore it
    # (it's the current message being processed)
    
    return pairs


def add_pair_to_buffer(
    buffer: List[Dict[str, str]], 
    pair: Dict[str, str], 
    max_size: int
) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]]]:
    """
    Add a Q&A pair to buffer. If buffer is full, return the oldest pair to be summarized.
    
    Args:
        buffer: Current buffer
        pair: Q&A pair to add
        max_size: Maximum buffer size
    
    Returns:
        Tuple of (new_buffer, popped_pair_if_full)
    """
    new_buffer = buffer.copy()
    new_buffer.append(pair)
    
    popped_pair = None
    if len(new_buffer) > max_size:
        popped_pair = new_buffer.pop(0)
    
    return new_buffer, popped_pair


def initialize_memory_from_messages(
    messages: List, 
    buffer_size: int = 3
) -> Tuple[List[Dict[str, str]], str]:
    """
    Initialize buffer and summary from existing conversation messages.
    
    Strategy:
    - Convert messages to pairs
    - Keep last N pairs in buffer (where N = buffer_size)
    - Older pairs are not summarized yet (summary = ""), will be summarized on-the-fly
    
    Args:
        messages: List of Message objects from database
        buffer_size: Maximum buffer size
    
    Returns:
        Tuple of (buffer, summary)
    """
    pairs = get_conversation_pairs(messages)
    
    if not pairs:
        return [], ""
    
    # Keep last N pairs in buffer
    buffer = pairs[-buffer_size:] if len(pairs) > buffer_size else pairs.copy()
    
    # For now, summary is empty (older pairs will be summarized on-the-fly when buffer rotates)
    # This is simpler and avoids needing to summarize all old messages at once
    summary = ""
    
    logger.info(f"Initialized memory: {len(buffer)} pairs in buffer, {len(pairs) - len(buffer)} older pairs")
    
    return buffer, summary


def build_enhanced_query(
    question: str,
    buffer: List[Dict[str, str]],
    summary: str
) -> str:
    """
    Build enhanced query with conversation context.
    
    Args:
        question: Current user question
        buffer: Conversation buffer (recent Q&A pairs)
        summary: Summary of older conversation
    
    Returns:
        Enhanced query string with context
    """
    parts = [question]
    
    if summary:
        parts.append(f"Previous conversation summary: {summary}")
    
    if buffer:
        buffer_text = format_buffer_for_context(buffer)
        parts.append(f"Recent conversation: {buffer_text}")
    
    return "\n\n".join(parts)


def calculate_query_similarity(
    query: str,
    conversation_context: str
) -> float:
    """
    Calculate similarity between query and conversation context using embedding.
    
    Args:
        query: Current user query
        conversation_context: Combined buffer + summary context
    
    Returns:
        Similarity score (0.0 - 1.0)
    """
    try:
        from src.rag.vectors.embeddings import encode_e5
        import numpy as np
        
        # Encode query
        query_emb = encode_e5([f"query: {query}"])[0]
        
        # Encode context
        context_emb = encode_e5([f"query: {conversation_context}"])[0]
        
        # Cosine similarity
        similarity = np.dot(query_emb, context_emb) / (
            np.linalg.norm(query_emb) * np.linalg.norm(context_emb)
        )
        
        return float(similarity)
    except Exception as e:
        logger.error(f"Error calculating query similarity: {e}")
        return 0.0


def calculate_pair_similarity(
    pair: Dict[str, str],
    conversation_context: str
) -> float:
    """
    Calculate similarity between Q&A pair and conversation context using embedding.
    
    Args:
        pair: Q&A pair {"user": "...", "bot": "..."}
        conversation_context: Combined buffer + summary context
    
    Returns:
        Similarity score (0.0 - 1.0)
    """
    try:
        from src.rag.vectors.embeddings import encode_e5
        import numpy as np
        
        # Encode pair text
        pair_text = f"User: {pair['user']}\nAssistant: {pair['bot']}"
        pair_emb = encode_e5([f"query: {pair_text}"])[0]
        
        # Encode context
        context_emb = encode_e5([f"query: {conversation_context}"])[0]
        
        # Cosine similarity
        similarity = np.dot(pair_emb, context_emb) / (
            np.linalg.norm(pair_emb) * np.linalg.norm(context_emb)
        )
        
        return float(similarity)
    except Exception as e:
        logger.error(f"Error calculating pair similarity: {e}")
        return 0.0


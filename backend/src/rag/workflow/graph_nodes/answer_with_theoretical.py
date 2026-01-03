"""
Answer with Theoretical Node
Node wrapper for theoretical knowledge-based answer generation logic
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes import generate_answer_with_theoretical

logger = logging.getLogger(__name__)


async def answer_with_theoretical_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Generate answer based on theoretical knowledge context.
    
    Args:
        state: State dict with question, theoretical_context, user_language
    
    Returns:
        Updated state with answer and done=True
    """
    question = state["question"]
    theoretical_context = state.get("theoretical_chunks", "")
    user_language = state.get("user_language", "vi")
    original_question = state.get("original_question")
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")

    logger.info(f"📚 Generating theoretical answer")
    logger.info(f"Theoretical context length: {len(theoretical_context)}")
    
    # Call logic function
    answer = await generate_answer_with_theoretical(
        question=question,
        theoretical_context=theoretical_context,
        user_language=user_language,
        original_question=original_question,
        conversation_buffer=conversation_buffer,
        summary_context=summary_context
    )
    
    # Update state with result
    state["answer"] = answer
    state["done"] = True
    
    logger.info(f"✅ Generated theoretical answer (length: {len(answer)})")
    
    return state

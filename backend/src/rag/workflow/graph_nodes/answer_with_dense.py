"""
Answer with Dense Node
Node wrapper for dense retrieval-based answer generation logic
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes.answer_with_dense import generate_answer_with_dense

logger = logging.getLogger(__name__)


async def answer_with_dense_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Generate answer based on dense retrieval context.
    
    Args:
        state: State dict with question, dense_context, slots, follow_up_questions
    
    Returns:
        Updated state with answer and done=True
    """
    question = state["question"]
    dense_context = state.get("dense_context", "")
    user_language = state.get("user_language", "en")
    original_question = state.get("original_question")
    slots = state.get("slots", {})
    follow_up_questions = state.get("follow_up_questions", [])
    relevant_missing_slots = state.get("relevant_missing_slots", [])

    logger.info("dense_context: %s", dense_context)
    
    # Call logic function
    answer = await generate_answer_with_dense(
        question=question,
        dense_context=dense_context,
        user_language=user_language,
        original_question=original_question,
        slots=slots,
        follow_up_questions=follow_up_questions,
        relevant_missing_slots=relevant_missing_slots
    )
    
    # Update state with result
    state["answer"] = answer
    state["done"] = True
    
    return state

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
    After generating answer, append optional follow-up questions if any.
    
    Args:
        state: State dict with question, dense_context, slots, follow_up_questions, optional_follow_up_questions
    
    Returns:
        Updated state with answer (including optional follow-ups) and done=True
    """
    question = state["question"]
    dense_context = state.get("dense_context", "")
    user_language = state.get("user_language", "en")
    original_question = state.get("original_question")
    slots = state.get("slots", {})
    follow_up_questions = state.get("follow_up_questions", [])
    relevant_missing_slots = state.get("relevant_missing_slots", [])
    optional_questions = state.get("optional_follow_up_questions", [])
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")

    logger.info("dense_context: %s", dense_context)
    
    # Call logic function (without follow_up_questions - we'll add them after)
    answer = await generate_answer_with_dense(
        question=question,
        dense_context=dense_context,
        user_language=user_language,
        original_question=original_question,
        slots=slots,
        follow_up_questions=[],  # Don't include in main answer
        relevant_missing_slots=[],
        conversation_buffer=conversation_buffer,
        summary_context=summary_context
    )
    
    # Append optional follow-up questions to the end of the answer
    if optional_questions:
        logger.info(f"📋 Appending {len(optional_questions)} optional follow-up questions to answer")
        
        # Add a natural transition (check language)
        if user_language == "vi":
            transition = "\n\nĐể tôi hiểu rõ hơn và hỗ trợ bạn tốt hơn, bạn có thể chia sẻ thêm:"
        else:
            transition = "\n\nTo better understand and support you, could you share more about:"
        
        answer += transition
        
        # Add questions as bullet points
        for i, question_text in enumerate(optional_questions, 1):
            answer += f"\n{i}. {question_text}"
        
        logger.info(f"✅ Added {len(optional_questions)} follow-up questions to answer")
    else:
        logger.info(f"ℹ️ No optional follow-up questions to add")
    
    # Update state with result
    state["answer"] = answer
    state["done"] = True
    
    return state

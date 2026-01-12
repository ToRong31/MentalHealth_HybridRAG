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
    
    NEW: Added error handling for retrieval failures
    
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
    retrieval_failed = state.get("retrieval_failed", False)

    logger.info(f"📚 Generating theoretical answer")
    logger.info(f"Theoretical context length: {len(theoretical_context)}")
    
    # Handle retrieval failure
    if retrieval_failed or not theoretical_context:
        logger.warning("⚠️ Retrieval failed or no context available")
        if user_language in ["vi", "vn"]:
            state["answer"] = "Xin lỗi, tôi đang gặp vấn đề kỹ thuật trong việc tra cứu thông tin. Bạn có thể thử hỏi lại sau một chút được không?"
        else:
            state["answer"] = "Sorry, I'm experiencing technical difficulties retrieving information. Could you please try again in a moment?"
        state["done"] = True
        return state
    
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

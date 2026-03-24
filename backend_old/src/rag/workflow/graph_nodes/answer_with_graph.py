"""
Answer with Graph Node
Node wrapper for graph-based answer generation logic
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes.answer_with_graph import generate_answer_with_graph

logger = logging.getLogger(__name__)


async def answer_with_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Generate answer based on graph context with conversation memory.
    
    Args:
        state: State dict with question, graph_context, conversation context, slots
    
    Returns:
        Updated state with answer and done=True
    """
    # Extract parameters from state
    question = state["question"]
    graph_context = state.get("combined_context") or state.get("graph_context", "")
    user_language = state.get("user_language", "en")
    original_question = state.get("original_question")
    slots = state.get("slots", {})
    follow_up_questions = state.get("follow_up_questions", [])
    relevant_missing_slots = state.get("relevant_missing_slots", [])
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    # Call logic function
    answer = await generate_answer_with_graph(
        question=question,
        graph_context=graph_context,
        user_language=user_language,
        original_question=original_question,
        slots=slots,
        follow_up_questions=follow_up_questions,
        relevant_missing_slots=relevant_missing_slots,
        conversation_buffer=buffer,
        summary_context=summary
    )
    
    # Check if needs apology prefix (from low confidence diagnostic)
    needs_apology = state.get("needs_apology_prefix", False)
    
    if needs_apology:
        if user_language in ["vi", "vn"]:
            apology = "Xin lỗi, do tôi chưa được cập nhật về các triệu chứng này nên không xác định được bệnh tâm lý cụ thể. Tuy nhiên, tôi có thể cung cấp một số hướng dẫn chung:\n\n"
        else:
            apology = "I apologize, as I haven't been updated on these specific symptoms and cannot identify a specific mental health condition. However, I can provide some general guidance:\n\n"
        answer = apology + answer
        logger.info("✅ Added apology prefix to graph answer (low diagnostic confidence)")
    
    # Update state with result
    state["answer"] = answer
    state["done"] = True
    
    return state

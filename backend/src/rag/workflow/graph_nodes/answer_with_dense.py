"""
Answer with Dense Node
Node wrapper for dense retrieval-based answer generation logic
"""
from typing import Dict, Any

from src.rag.llm.answer_nodes.answer_with_dense import generate_answer_with_dense


async def answer_with_dense_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Generate answer based on dense retrieval context.
    
    Args:
        state: State dict with question and dense_context
    
    Returns:
        Updated state with answer and done=True
    """
    question = state["question"]
    dense_context = state.get("dense_context", "")
    
    # Call logic function
    answer = await generate_answer_with_dense(
        question=question,
        dense_context=dense_context
    )
    
    # Update state with result
    state["answer"] = answer
    state["done"] = True
    
    return state

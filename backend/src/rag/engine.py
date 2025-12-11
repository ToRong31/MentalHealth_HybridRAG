"""
RAG engine - Entry point for running the graph workflow.
Exposes the run_graph() function for chat service.
"""
import asyncio
import logging
from typing import Dict, Any

from .workflow.workflow import KGState


logger = logging.getLogger(__name__)


async def run_graph(graph, question: str) -> Dict[str, Any]:
    """
    Run the RAG graph workflow with a user question (async version).
    
    Args:
        graph: Compiled LangGraph workflow
        question: User's question
    
    Returns:
        Final state dictionary with answer and metadata
    """
    initial_state: KGState = {
        "question": question,
        "original_question": "",
        "user_language": "en",
        "is_mental_health_related": False,
        "is_high_risk": False,
        "query_embedding": [],
        "anchors": [],
        "nodes": [],
        "rels": [],
        "graph_context": "",
        "dense_context": "",
        "answer": "",
        "done": False,
        # Slot Filling Data (will be populated by slot_filling_node)
        "slots": None,
        "missing_slots": None,
        "relevant_missing_slots": None,
        "follow_up_questions": None,
        # Timing tracking (will be set by translate_question_node)
        "parallel_start_time": None,
    }
    
    try:
        # Use ainvoke for async workflow
        final_state = await graph.ainvoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Error running RAG graph: {e}", exc_info=True)
        return {
            "answer": "I'm sorry, I encountered an error processing your request.",
            "is_mental_health_related": False,
            "is_high_risk": False,
        }

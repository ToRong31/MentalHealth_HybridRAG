"""
LangGraph Nodes for Graph-based RAG Workflow
Refactored to use modular components
"""
from typing import Dict, Any
import logging

from .state import KGState
from src.vectors.embeddings import encode_e5
from src.retrieval.graph_retrieval import graph_retrieval
from src.retrieval.dense_retrieval import DenseRetrievel
from src.llm.translator import GeminiTranslator, get_translator
from src.llm.answer_nodes import (
    safety_check_node,
    crisis_response_node,
    not_mental_health_node,
    answer_with_graph_node
)

logger = logging.getLogger(__name__)


def translate_question_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch question sang tiếng Anh nếu cần
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'original_question', 'question' (translated), 'user_language'
    """
    question = state["question"]
    
    # Detect language
    lang = GeminiTranslator.detect_language(question)
    state["user_language"] = lang
    state["original_question"] = question
    
    logger.info(f"Detected language: {lang}")
    
    if lang == 'vi':
        # Dịch sang tiếng Anh để xử lý
        logger.info(f"Translating VI->EN: {question[:50]}...")
        translator = get_translator()
        translated = translator.vi_to_en(question)
        state["question"] = translated
        logger.info(f"Translated to: {translated[:50]}...")
    else:
        logger.info(f"Question is in English, skipping translation")
    
    return state


def translate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch answer về ngôn ngữ của user
    
    Args:
        state: KGState with 'answer', 'user_language'
    
    Returns:
        Updated state with translated 'answer'
    """
    if state.get("skip_translation"):
        logger.info("Skipping translation step for non-graph route")
        return state

    answer = state.get("answer", "")
    user_lang = state.get("user_language", "en")
    
    logger.info(f"User language: {user_lang}")
    
    if user_lang == 'vi' and answer:
        # Dịch answer về tiếng Việt
        logger.info(f"Translating EN->VI: {answer[:50]}...")
        translator = get_translator()
        translated = translator.en_to_vi(answer)
        state["answer"] = translated
        logger.info(f"Translated to: {translated[:50]}...")
    else:
        logger.info(f"Answer stays in English")
    
    return state
# --- Encoding node ---

def encode_node(state: KGState) -> KGState:
    """
    Encode query to embedding vector
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'query_embedding'
    """
    q = state["question"]
    emb = encode_e5([f"query: {q}"])[0]
    state["query_embedding"] = emb.tolist()
    return state


# --- Retrieval node ---

def graph_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve graph context using GraphRetrieval
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """
    question = state["question"]
    
    # Use GraphRetrieval to get context
    result = graph_retrieval.retrieve(question)
    
    # Update state
    state["graph_context"] = result.context
    state["anchors"] = result.metadata.get("anchors", [])
    state["nodes_count"] = result.metadata.get("nodes_count", 0)
    state["rels_count"] = result.metadata.get("rels_count", 0)
    
    return state

def dense_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve relevant nodes using DenseRetrieval
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """

    question = state["question"]
    
    dense_retriever = DenseRetrievel()
    results = dense_retriever.retrieve([question], top_k=10)
    

    
    state["dense_context"] = results

    return state

# --- Export all nodes ---

__all__ = [

    # Translator
    'translate_question_node',
    'translate_answer_node',
    
    # Safety nodes (from llm.answer_nodes)
    'safety_check_node',
    'crisis_response_node',
    'not_mental_health_node',
    
    # Encoding
    'encode_node',
    
    # Retrieval
    'graph_retrieval_node',
    'dense_retrieval_node',
    
    # Answer generation
    'answer_with_graph_node',
]

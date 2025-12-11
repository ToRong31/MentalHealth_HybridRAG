"""
LangGraph Nodes for Graph-based RAG Workflow
Refactored to use modular components with async support
"""
import asyncio
from typing import Dict, Any
import logging

from .state import KGState
from src.rag.vectors.embeddings import encode_e5
from src.rag.retrieval.graph_retrieval import graph_retrieval
from src.rag.retrieval.dense_retrieval import dense_retrieval
from src.rag.retrieval.hybrid_retrieval import hybrid_retrieval
from src.rag.llm.translator import GeminiTranslator, get_translator

logger = logging.getLogger(__name__)


async def translate_question_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch question sang tiếng Anh nếu cần (async version)
    Set timestamp for parallel execution tracking
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'original_question', 'question' (translated), 'user_language', 'parallel_start_time'
    """
    import time
    
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
    
    # Set timestamp when parallel execution starts (safety_check + slot_filling)
    state["parallel_start_time"] = time.time()
    logger.debug(f"Set parallel_start_time: {state['parallel_start_time']}")
    
    return state


async def translate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch answer về ngôn ngữ của user (async version)
    
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

async def encode_node(state: KGState) -> KGState:
    """
    Encode query to embedding vector (async version)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'query_embedding'
    """
    q = state["question"]
    # Run encoding in executor to avoid blocking
    loop = asyncio.get_event_loop()
    emb = await loop.run_in_executor(None, lambda: encode_e5([f"query: {q}"])[0])
    state["query_embedding"] = emb.tolist()
    return state


# --- Retrieval node ---

async def graph_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve graph context using GraphRetrieval with smart waiting for slots
    
    Logic:
    - Nếu slots có sẵn → execute ngay
    - Nếu chưa có → đợi tối đa 5 giây
    - Sau 7 giây tổng cộng → proceed với defaults
    
    Args:
        state: KGState with 'question', 'parallel_start_time', 'slots'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """
    import time
    from src.rag.slots.utils import get_default_slots
    
    question = state["question"]
    parallel_start_time = state.get("parallel_start_time")
    slots = state.get("slots")
    
    # Check nếu slots chưa có
    if slots is None:
        logger.info("Slots not ready, waiting for slot_filling...")
        
        # Tính thời gian đã trôi qua
        elapsed_time = 0.0
        if parallel_start_time:
            elapsed_time = time.time() - parallel_start_time
        
        # Tính thời gian còn lại để đợi
        # - Đợi tối đa 5 giây
        # - Nhưng tổng không quá 7 giây từ khi bắt đầu
        max_wait_time = min(5.0, max(0, 7.0 - elapsed_time))
        
        if max_wait_time > 0:
            logger.info(f"Waiting up to {max_wait_time:.2f}s for slots (elapsed: {elapsed_time:.2f}s)")
            
            # Poll slots mỗi 0.1 giây
            wait_interval = 0.1
            waited_time = 0.0
            
            while waited_time < max_wait_time:
                await asyncio.sleep(wait_interval)
                waited_time += wait_interval
                
                # Check lại slots từ state
                if state.get("slots") is not None:
                    slots = state.get("slots")
                    logger.info(f"Slots ready after {waited_time:.2f}s wait")
                    break
                
                # Check tổng thời gian
                if parallel_start_time:
                    total_elapsed = time.time() - parallel_start_time
                    if total_elapsed >= 7.0:
                        logger.warning(f"Total time exceeded 7s ({total_elapsed:.2f}s), proceeding without slots")
                        break
            
            # Nếu vẫn chưa có sau khi đợi
            if state.get("slots") is None:
                logger.warning("Slots still not ready after waiting, using defaults")
                state["slots"] = get_default_slots()
                state["missing_slots"] = []
                state["relevant_missing_slots"] = []
                state["follow_up_questions"] = []
        else:
            # Đã quá 7 giây tổng cộng
            logger.warning(f"Total time already exceeded 7s ({elapsed_time:.2f}s), proceeding without slots")
            state["slots"] = get_default_slots()
            state["missing_slots"] = []
            state["relevant_missing_slots"] = []
            state["follow_up_questions"] = []
    else:
        logger.info("Slots ready, proceeding immediately")
    
    # Lấy slots cuối cùng (có thể đã được set trong wait loop)
    slots = state.get("slots", get_default_slots())
    
    # Enhance query với slots nếu có thông tin hữu ích
    enhanced_query = question
    if slots:
        emotion = slots.get("emotion", [])
        trigger = slots.get("trigger")
        
        if emotion:
            enhanced_query += f" emotions: {', '.join(emotion)}"
        if trigger:
            enhanced_query += f" trigger: {trigger}"
    
    # Use async GraphRetrieval to get context
    result = await graph_retrieval.retrieve_async(enhanced_query)
    
    # Update state
    state["graph_context"] = result.context
    state["anchors"] = result.metadata.get("anchors", [])
    state["nodes_count"] = result.metadata.get("nodes_count", 0)
    state["rels_count"] = result.metadata.get("rels_count", 0)
    
    return state

async def dense_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve relevant nodes using DenseRetrieval (async version)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'dense_context'
    """
    question = state["question"]
    
    # Use async DenseRetrieval to get context
    results = await dense_retrieval.retrieve_async(question, top_k=2)
    
    state["dense_context"] = results.context
    
    return state


async def hybrid_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve context using both graph and dense retrieval in parallel (hybrid search)
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'combined_context' and metadata from both retrievers
    """
    question = state["question"]
    
    logger.info(f"Starting hybrid retrieval for: {question[:50]}...")
    
    # Use HybridRetrieval to get combined context
    result = await hybrid_retrieval.retrieve_async(question)
    
    # Update state with combined context
    state["combined_context"] = result.context
    state["graph_context"] = result.metadata.get("graph_metadata", {}).get("context", "")
    state["dense_context"] = result.metadata.get("dense_metadata", {}).get("context", "")
    state["retrieval_metadata"] = result.metadata
    
    logger.info(f"Hybrid retrieval completed in {result.metadata.get('execution_time', 0):.2f}s")
    
    return state

# --- Export all nodes ---

__all__ = [

    # Translator
    'translate_question_node',
    'translate_answer_node',
    
    # Encoding
    'encode_node',
    
    # Retrieval
    'graph_retrieval_node',
    'dense_retrieval_node',
    'hybrid_retrieval_node',
    
    # (Answer generation nodes are in llm/answer_nodes.py)
]

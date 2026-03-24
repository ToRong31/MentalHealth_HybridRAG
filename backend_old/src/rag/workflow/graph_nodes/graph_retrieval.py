"""
Graph Retrieval Node
Retrieves graph context using GraphRetrieval with smart waiting for slots
"""
import asyncio
import logging
import time

from ..state import KGState
from src.rag.retrieval.graph_retrieval import graph_retrieval
from src.rag.utils.memory import build_enhanced_query
from src.rag.utils.slots import get_default_slots

logger = logging.getLogger(__name__)


async def graph_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve graph context using GraphRetrieval with smart waiting for slots.
    Uses rewritten_query from query_rewriter node which includes slots + conversation context.
    
    Logic:
    - Nếu slots có sẵn → execute ngay
    - Nếu chưa có → đợi tối đa 5 giây
    - Sau 7 giây tổng cộng → proceed với defaults
    - Uses rewritten_query if available (from query_rewriter node)
    
    Args:
        state: KGState with 'question', 'rewritten_query', 'parallel_start_time', 'slots'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """
    original_question = state["question"]
    rewritten_query = state.get("rewritten_query")
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
    
    # Use rewritten query from query_rewriter node (includes slots + conversation context)
    # Falls back to original question if rewriter hasn't run
    query_for_retrieval = rewritten_query if rewritten_query else original_question
    
    if rewritten_query:
        logger.info(f"🔍 Using rewritten query for graph retrieval")
        logger.debug(f"Rewritten: {rewritten_query[:100]}...")
    else:
        logger.info(f"🔍 Using original query for graph retrieval (no rewrite available)")
    
    result = await graph_retrieval.retrieve_async(
        query_for_retrieval,
        slots=slots,
        original_query=original_question  # Keep original for reranking if needed
    )
    
    # Update state
    state["graph_context"] = result.context
    state["anchors"] = result.metadata.get("anchors", [])
    state["nodes_count"] = result.metadata.get("nodes_count", 0)
    state["rels_count"] = result.metadata.get("rels_count", 0)
    
    return state

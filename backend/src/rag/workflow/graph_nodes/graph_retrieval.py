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
    Conditional enhancement: enhance query nếu follow_up/topic_change, không enhance nếu off_topic.
    
    Logic:
    - Nếu slots có sẵn → execute ngay
    - Nếu chưa có → đợi tối đa 5 giây
    - Sau 7 giây tổng cộng → proceed với defaults
    - Conditional query enhancement dựa trên should_enhance_query và query_type
    
    Args:
        state: KGState with 'question', 'parallel_start_time', 'slots', 'query_type', 'should_enhance_query', 'conversation_buffer', 'summary_context'
    
    Returns:
        Updated state with 'graph_context', 'anchors', 'nodes', 'rels'
    """
    original_question = state["question"]
    query_type = state.get("query_type")
    should_enhance = state.get("should_enhance_query")
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
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
    
    # Conditional query enhancement for retrieval
    # Enhance query nếu follow_up hoặc topic_change
    # Không enhance nếu off_topic (nhưng off_topic đã bị reject ở safety check)
    if should_enhance and query_type in ["follow_up", "topic_change"]:
        # Build enhanced query with conversation context
        enhanced_question = build_enhanced_query(original_question, buffer, summary)
        # Use enhanced query for Milvus search, but original query for reranking
        logger.info(f"Enhanced query for retrieval (type: {query_type})")
        logger.debug(f"Enhanced query: {enhanced_question[:100]}...")
        result = await graph_retrieval.retrieve_async(
            enhanced_question, 
            slots=slots,
            original_query=original_question  # Use original for reranking
        )
    else:
        # Use original query (off_topic or first message)
        if query_type == "off_topic":
            logger.info("Using original query for retrieval (off_topic)")
        else:
            logger.info("Using original query for retrieval (no enhancement needed)")
        result = await graph_retrieval.retrieve_async(original_question, slots=slots)
    
    # Update state
    state["graph_context"] = result.context
    state["anchors"] = result.metadata.get("anchors", [])
    state["nodes_count"] = result.metadata.get("nodes_count", 0)
    state["rels_count"] = result.metadata.get("rels_count", 0)
    
    return state

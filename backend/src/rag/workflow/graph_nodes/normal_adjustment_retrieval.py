"""
Normal Coping Retrieval Node
Retrieves content about normal stress responses and coping strategies
(NOT disorder content)
"""

import logging
from ..state import KGState
from src.rag.retrieval.graph_retrieval import graph_retrieval

logger = logging.getLogger(__name__)


async def normal_coping_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve normal stress response and coping strategy content.
    
    This node is called when assessment_category = "normal_response".
    Focuses on:
    - Normalizing the experience
    - Coping strategies
    - Psychoeducation about normal vs disorder
    - Reassurance
    
    Args:
        state: KGState with 'question', 'rewritten_query', 'slots'
    
    Returns:
        Updated state with 'graph_context'
    """
    original_question = state["question"]
    rewritten_query = state.get("rewritten_query", original_question)
    slots = state.get("slots", {})
    assessment_category = state.get("assessment_category", "")
    
    logger.info("=" * 80)
    logger.info("[NORMAL COPING RETRIEVAL] Starting normal stress content retrieval")
    logger.info(f"[QUERY] {rewritten_query}")
    logger.info(f"[ASSESSMENT] {assessment_category}")
    logger.info("=" * 80)
    
    try:
        # Build enhanced query focusing on normal responses
        trigger = slots.get("recent_life_events", "")
        emotion = slots.get("emotion", "")
        
        # Enhance query with normal stress keywords
        enhanced_query = f"{rewritten_query}. "
        
        if trigger:
            enhanced_query += f"Stress bình thường khi {trigger}. "
        if emotion:
            enhanced_query += f"Cảm xúc {emotion} bình thường. "
        
        enhanced_query += "Phản ứng tự nhiên không phải rối loạn. Cách đối phó và quản lý stress hằng ngày."
        
        logger.info(f"[ENHANCED QUERY] {enhanced_query}")
        
        # Retrieve from graph (will get normal_responses nodes if they exist)
        result = await graph_retrieval(
            question=enhanced_query,
            top_k=5,  # Get top 5 most relevant nodes
            expand_depth=1
        )
        
        graph_context = result.get("graph_context", "")
        anchors = result.get("anchors", [])
        nodes = result.get("nodes", [])
        rels = result.get("rels", [])
        
        # Update state
        state["graph_context"] = graph_context
        state["anchors"] = anchors
        state["nodes"] = nodes
        state["rels"] = rels
        
        logger.info(f"[RETRIEVAL RESULT] Retrieved {len(nodes)} nodes, {len(rels)} relationships")
        logger.info(f"[CONTEXT LENGTH] {len(graph_context)} characters")
        
        if not graph_context or len(graph_context) < 100:
            logger.warning("[WARNING] Retrieved content is too short or empty")
            # Fallback: provide generic normal stress response
            state["graph_context"] = _get_fallback_normal_content(slots)
        
    except Exception as e:
        logger.error(f"[ERROR] Normal coping retrieval failed: {e}", exc_info=True)
        # Fallback
        state["graph_context"] = _get_fallback_normal_content(slots)
    
    logger.info("=" * 80)
    return state


async def adjustment_retrieval_node(state: KGState) -> KGState:
    """
    Retrieve adjustment reaction and life event coping content.
    
    This node is called when assessment_category = "adjustment_reaction".
    Focuses on:
    - Adjustment to life events
    - Timeline for recovery
    - When adjustment becomes disorder
    - Support strategies
    
    Args:
        state: KGState with 'question', 'rewritten_query', 'slots'
    
    Returns:
        Updated state with 'graph_context'
    """
    original_question = state["question"]
    rewritten_query = state.get("rewritten_query", original_question)
    slots = state.get("slots", {})
    assessment_category = state.get("assessment_category", "")
    
    logger.info("=" * 80)
    logger.info("[ADJUSTMENT RETRIEVAL] Starting adjustment reaction content retrieval")
    logger.info(f"[QUERY] {rewritten_query}")
    logger.info(f"[ASSESSMENT] {assessment_category}")
    logger.info("=" * 80)
    
    try:
        # Build enhanced query focusing on adjustment
        trigger = slots.get("recent_life_events", "")
        duration = slots.get("duration", "")
        
        # Enhance query with adjustment keywords
        enhanced_query = f"{rewritten_query}. "
        
        if trigger:
            enhanced_query += f"Phản ứng điều chỉnh sau {trigger}. "
        if duration:
            enhanced_query += f"Kéo dài {duration}. "
        
        enhanced_query += "Adjustment reaction. Quá trình thích nghi tự nhiên. Cách hỗ trợ bản thân trong giai đoạn điều chỉnh."
        
        logger.info(f"[ENHANCED QUERY] {enhanced_query}")
        
        # Retrieve from graph
        result = await graph_retrieval(
            question=enhanced_query,
            top_k=5,
            expand_depth=1
        )
        
        graph_context = result.get("graph_context", "")
        anchors = result.get("anchors", [])
        nodes = result.get("nodes", [])
        rels = result.get("rels", [])
        
        # Update state
        state["graph_context"] = graph_context
        state["anchors"] = anchors
        state["nodes"] = nodes
        state["rels"] = rels
        
        logger.info(f"[RETRIEVAL RESULT] Retrieved {len(nodes)} nodes, {len(rels)} relationships")
        logger.info(f"[CONTEXT LENGTH] {len(graph_context)} characters")
        
        if not graph_context or len(graph_context) < 100:
            logger.warning("[WARNING] Retrieved content is too short or empty")
            # Fallback: provide generic adjustment content
            state["graph_context"] = _get_fallback_adjustment_content(slots)
        
    except Exception as e:
        logger.error(f"[ERROR] Adjustment retrieval failed: {e}", exc_info=True)
        # Fallback
        state["graph_context"] = _get_fallback_adjustment_content(slots)
    
    logger.info("=" * 80)
    return state


def _get_fallback_normal_content(slots: dict) -> str:
    """Generate fallback content for normal stress response"""
    trigger = slots.get("recent_life_events", "tình huống này")
    duration = slots.get("duration", "")
    
    content = f"""
**Phản Ứng Stress Bình Thường**

Những gì bạn đang trải qua với {trigger} là phản ứng stress HOÀN TOÀN BÌNH THƯỜNG và phổ biến. 
Đây KHÔNG phải là rối loạn tâm lý.

**Đặc điểm của stress bình thường:**
- Có nguyên nhân rõ ràng và cụ thể
- Thời gian ngắn (thường vài ngày đến vài tuần)
- Giảm dần khi tình huống được giải quyết
- Không ảnh hưởng nghiêm trọng đến sinh hoạt hàng ngày

**Cách đối phó hiệu quả:**
1. **Chấp nhận cảm xúc:** Lo lắng/căng thẳng trước {trigger} là bình thường
2. **Chuẩn bị tốt:** Lập kế hoạch rõ ràng và chuẩn bị kỹ càng
3. **Thở sâu:** Kỹ thuật 4-7-8 (hít 4 giây, giữ 7 giây, thở ra 8 giây)
4. **Nghỉ ngơi:** Ngủ đủ giấc, ăn uống đều đặn
5. **Chia sẻ:** Nói chuyện với người thân giúp giảm áp lực

**Quan trọng:** Cảm giác này sẽ tự khỏi sau khi tình huống qua đi. Không cần thuốc hay trị liệu chuyên sâu.
"""
    return content


def _get_fallback_adjustment_content(slots: dict) -> str:
    """Generate fallback content for adjustment reaction"""
    trigger = slots.get("recent_life_events", "biến cố này")
    duration = slots.get("duration", "")
    
    content = f"""
**Phản Ứng Điều Chỉnh (Adjustment Reaction)**

Những gì bạn đang trải qua sau {trigger} là phản ứng điều chỉnh - một quá trình TỰ NHIÊN và BÌNH THƯỜNG 
khi cơ thể/tâm lý thích nghi với thay đổi lớn trong cuộc sống.

**Đặc điểm của phản ứng điều chỉnh:**
- Bắt đầu trong vòng 3 tháng sau biến cố
- Triệu chứng có thể rõ rệt nhưng CHƯA ĐỦ tiêu chuẩn của rối loạn lớn
- Thường TỰ KHỎI trong 6 tháng sau khi thích nghi được
- Mức độ khó khăn tương xứng với mức độ nghiêm trọng của biến cố

**Cách hỗ trợ bản thân:**
1. **Cho phép thời gian:** Thích nghi cần thời gian, đừng vội vàng
2. **Duy trì thói quen:** Giữ lịch trình ăn, ngủ, vận động đều đặn
3. **Kết nối:** Chia sẻ với bạn bè, gia đình, hoặc nhóm hỗ trợ
4. **Tự chăm sóc:** Ưu tiên sức khỏe thể chất và tinh thần
5. **Tránh quyết định lớn:** Hoãn các quyết định quan trọng trong 3-6 tháng đầu

**Khi nào cần gặp chuyên gia:**
- Triệu chứng quá nặng, ảnh hưởng nghiêm trọng đến công việc/quan hệ
- Không cải thiện sau 6 tháng
- Có suy nghĩ tự hại

Nếu không thuộc các trường hợp trên, bạn đang trong quá trình điều chỉnh bình thường.
"""
    return content

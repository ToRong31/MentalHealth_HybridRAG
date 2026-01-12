"""
Crisis Response Nodes
Multi-stage adaptive crisis response system
"""
from typing import Dict, Any
import logging

from src.rag.llm.answer_nodes.crisis_response import get_crisis_response_message
from src.rag.llm.llm_gemini import LLMClient

logger = logging.getLogger(__name__)

# Initialize LLM client for classifier
llm = LLMClient()


# ============================================================================
# STAGE 1: IMMEDIATE SAFETY RESPONSE
# ============================================================================

async def crisis_immediate_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 1: Immediate safety intervention with hotlines
    
    Triggers: First time high-risk detected
    Goal: Show hotlines + empathetic opening + safety check question
    
    Sets: crisis_stage=1, crisis_response_count++, done=False
    Next: Routes to crisis_follow_up_classifier
    """
    crisis_level = state.get("crisis_level", "high")
    crisis_indicators = state.get("crisis_indicators", [])
    
    logger.warning(f"[CRISIS STAGE 1] Immediate response triggered. Level: {crisis_level}")
    logger.warning(f"[CRISIS STAGE 1] Indicators: {crisis_indicators}")
    
    # Get base crisis message (hotlines template)
    base_message = get_crisis_response_message()
    
    # Simple opening without empathy (base_message already has it)
    opening = "Tôi nhận thấy bạn đang trải qua một thời điểm rất khó khăn."
    
    # Add safety check question
    safety_question = "\n\n❓ Bạn có thể cho tôi biết bạn đang ở đâu và có ai ở cùng không?"
    
    if crisis_level == "critical":
        # More urgent for critical
        opening = "🚨 **TÌNH HUỐNG KHẨN CẤP**\n\nBạn đang trong tình huống nguy hiểm và cần được hỗ trợ NGAY LẬP TỨC."
        safety_question = "\n\n⚠️ **Bạn có đang an toàn ngay lúc này không?**"
    
    message = opening + "\n\n" + base_message + safety_question
    
    # Update state
    state["answer"] = message
    state["skip_translation"] = True
    state["done"] = False  # CRITICAL: Allow continuation
    state["crisis_stage"] = 1
    state["crisis_response_count"] = state.get("crisis_response_count", 0) + 1
    state["user_acknowledged_crisis"] = False
    
    logger.info(f"[CRISIS STAGE 1] Response sent. Count: {state['crisis_response_count']}")
    
    return state


# ============================================================================
# STAGE 2: FOLLOW-UP CLASSIFIER
# ============================================================================

async def crisis_follow_up_classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 2: Classify user's response after crisis message
    
    Classifications:
    - "immediate_danger": User confirms in immediate danger → Escalate
    - "seeking_help": User wants to talk/needs support → Contextual support
    - "declining_help": User defensive/resistant → Gentle persistence
    - "de_escalated": User calmer/risk decreased → Transition to normal
    
    Sets: crisis_follow_up_classification
    """
    question = state.get("question", "")
    buffer = state.get("conversation_buffer", [])
    crisis_indicators = state.get("crisis_indicators", [])
    crisis_level = state.get("crisis_level", "high")
    
    logger.info(f"[CRISIS CLASSIFIER] Analyzing user response: {question[:100]}...")
    
    # Format recent history
    recent = buffer[-4:] if len(buffer) > 4 else buffer
    history_str = "\n".join([
        f"{msg.get('type', 'unknown')}: {msg.get('content', '')}" 
        for msg in recent 
        if isinstance(msg, dict) and msg.get('content')
    ])
    
    # LLM classification prompt
    prompt = f"""Bạn là chuyên gia crisis intervention. Phân loại phản ứng của user sau khi nhận crisis intervention message.

CRISIS INDICATORS ĐÃ PHÁT HIỆN: {', '.join(crisis_indicators) if crisis_indicators else 'None'}
CRISIS LEVEL: {crisis_level}

CONVERSATION HISTORY:
{history_str}

USER RESPONSE MỚI NHẤT: {question}

NHIỆM VỤ: Classify user response vào 1 trong 4 categories:

1. **immediate_danger** - User confirm đang trong nguy hiểm immediate:
   - Mention về plan cụ thể, means, intent
   - Đang có action nguy hiểm (đã uống thuốc, cầm dao, etc.)
   - Từ chối gọi hotline VÀ có nguy cơ cao
   - Examples: "Tôi đã chuẩn bị thuốc ngủ", "Tôi đang ở mái nhà"

2. **seeking_help** - User muốn support/nói chuyện:
   - Cần ai đó lắng nghe, hiểu
   - Muốn tìm cách đối phó
   - Engage với questions, sẵn sàng chia sẻ
   - Examples: "Tôi cần ai đó hiểu tôi", "Làm sao để bớt đau khổ?"

3. **declining_help** - User defensive/từ chối:
   - Từ chối support, resistant
   - Defensive, angry tone
   - Deflecting, minimizing
   - Examples: "Không cần bạn can thiệp", "Tôi ổn rồi, thôi"

4. **de_escalated** - Risk giảm, user calm hơn:
   - Cảm xúc ổn định hơn
   - Sẵn sàng nói về vấn đề khác
   - Acknowledge feeling better
   - Examples: "Tôi ổn hơn rồi", "Giờ tôi muốn nói về công việc"

OUTPUT FORMAT (JSON):
{{
    "classification": "immediate_danger" | "seeking_help" | "declining_help" | "de_escalated",
    "confidence": "high" | "medium" | "low",
    "reasoning": "Brief explanation in Vietnamese"
}}

CRITICAL: Respond ONLY with valid JSON. No markdown, no code blocks."""

    try:
        # Use the global llm instance
        response = llm.invoke(prompt)
        
        # Parse JSON response
        import json
        result = json.loads(response if isinstance(response, str) else str(response))
        
        classification = result.get("classification", "seeking_help")
        confidence = result.get("confidence", "medium")
        reasoning = result.get("reasoning", "")
        
        logger.info(f"[CRISIS CLASSIFIER] Classification: {classification} (confidence: {confidence})")
        logger.info(f"[CRISIS CLASSIFIER] Reasoning: {reasoning}")
        
    except Exception as e:
        logger.error(f"[CRISIS CLASSIFIER] Error: {e}. Using fallback classification.")
        
        # Fallback: keyword-based classification
        q_lower = question.lower()
        
        # Check for immediate danger keywords
        danger_keywords = ["đã chuẩn bị", "đang cầm", "sắp", "ngay bây giờ", "không thể", "không ai"]
        if any(k in q_lower for k in danger_keywords):
            classification = "immediate_danger"
        
        # Check for seeking help keywords
        elif any(k in q_lower for k in ["cần", "giúp", "làm sao", "muốn nói", "có thể"]):
            classification = "seeking_help"
        
        # Check for declining keywords
        elif any(k in q_lower for k in ["không cần", "thôi", "ổn rồi", "đừng", "để tôi"]):
            classification = "declining_help"
        
        # Default to seeking help (safest fallback)
        else:
            classification = "seeking_help"
        
        confidence = "low"
        reasoning = "Fallback classification due to parsing error"
    
    # Store classification in state
    state["crisis_follow_up_classification"] = classification
    state["user_acknowledged_crisis"] = True
    
    return state


# ============================================================================
# STAGE 3A: ESCALATION (Immediate Danger)
# ============================================================================

async def crisis_escalation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 3A: Stronger intervention for immediate danger
    
    Triggers: User confirms immediate danger
    Features: More urgent language, alternative actions, limited turns
    """
    crisis_response_count = state.get("crisis_response_count", 0)
    
    logger.critical(f"[CRISIS ESCALATION] Immediate danger confirmed. Count: {crisis_response_count}")
    
    # Check if max escalations reached
    if crisis_response_count >= 2:
        logger.critical(f"[CRISIS ESCALATION] Max escalations reached (2). Ending with final message.")
        message = """🚨 **VUI LÒNG GỌI HOTLINE KHẨN CẤP**

📞 **115** (Cấp cứu y tế - 24/7) hoặc **1800 599 913** (Tư vấn tâm lý)

Tôi là chatbot và không thể cung cấp hỗ trợ khẩn cấp mà bạn cần ngay lúc này. 

**Hành động quan trọng nhất:** Gọi hotline hoặc đến bệnh viện gần nhất.

🙏 Bạn xứng đáng được giúp đỡ. Xin hãy tìm đến chuyên gia."""
        
        state["answer"] = message
        state["skip_translation"] = True
        state["done"] = True  # End conversation
        state["crisis_stage"] = None  # Clear crisis stage
        return state
    
    # Continue escalation (count < 2)
    message = """🚨 **TÌNH HUỐNG KHẨN CẤP**

Bạn đang trong tình huống nguy hiểm và cần được hỗ trợ NGAY LẬP TỨC từ chuyên gia.


📞 **HÃY GỌI NGAY:**
• **115** - Cấp cứu y tế (miễn phí, 24/7)
• **113** - Cảnh sát (nếu cần bảo vệ)
• **1800 599 913** - Tư vấn tâm lý khẩn cấp

**Nếu bạn không thể gọi, hãy:**
1. Nhắn tin cho người thân: "Tôi cần giúp đỡ khẩn cấp"
2. Đi đến bệnh viện gần nhất
3. Gọi xe cứu thương hoặc taxi đến phòng cấp cứu

💡 **Tôi là chatbot và không thể thay thế sự hỗ trợ khẩn cấp từ con người.**

⚠️ Bạn có đang an toàn ngay lúc này không?"""

    state["answer"] = message
    state["skip_translation"] = True
    state["done"] = False  # Allow one more response
    state["crisis_stage"] = 2
    state["crisis_response_count"] = crisis_response_count + 1
    
    return state


# ============================================================================
# STAGE 3B: CONTEXTUAL SUPPORT (Seeking Help)
# ============================================================================

async def crisis_contextual_support_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 3B: Contextual support with coping strategies from KG
    
    Triggers: User wants support/help
    Features: Retrieve coping strategies, grounding techniques, validation
    """
    indicators = state.get("crisis_indicators", [])
    question = state.get("question", "")
    buffer = state.get("conversation_buffer", [])
    empathy = state.get("empathy_preamble_vi", "")
    
    logger.info(f"[CRISIS SUPPORT] Providing contextual support. Indicators: {indicators}")
    
    # For now, use static coping strategies
    # TODO: Integrate with KG retrieval in future
    
    # Build support message based on indicators
    indicator_set = set([ind.lower() for ind in indicators])
    
    coping_strategies = ""
    if "suicide" in indicator_set or "self-harm" in indicator_set:
        coping_strategies = """💡 **NGAY BÂY GIỜ, bạn có thể thử:**

1. **Kỹ thuật 5-4-3-2-1** (Grounding):
   - Nhìn 5 thứ xung quanh bạn
   - Chạm vào 4 bề mặt khác nhau
   - Nghe 3 âm thanh
   - Ngửi 2 mùi hương
   - Nếm 1 vị
   
   → Giúp bạn quay về hiện tại, giảm overwhelming feelings

2. **Breathing 4-7-8**:
   - Hít vào 4 giây
   - Giữ 7 giây  
   - Thở ra 8 giây
   - Lặp lại 4 lần
   
   → Làm chậm nhịp tim, giảm panic

3. **Temperature shock**:
   - Rửa mặt bằng nước lạnh
   - Hoặc giữ ice cube trong tay
   
   → Cơ thể tập trung vào cảm giác này thay vì emotions"""
    
    else:
        # Generic coping for other crisis types
        coping_strategies = """💡 **MỘT SỐ KỸ THUẬT CÓ THỂ GIÚP NGAY:**

1. **Deep breathing**: Hít thở sâu 4-7-8
2. **Grounding**: Chạm vào vật xung quanh, cảm nhận texture
3. **Movement**: Đi bộ nhẹ, duỗi người
4. **Distraction**: Nghe nhạc, xem video nhẹ nhàng"""
    
    message = f"""Tôi nghe thấy bạn đang trải qua đau khổ rất lớn, và tôi hiểu rằng có những lúc cảm giác này khiến mọi thứ như không còn lối thoát. Cảm ơn bạn đã chia sẻ với tôi.

{coping_strategies}

🤝 Nếu các kỹ thuật này không giúp được, hoặc cảm giác quá nặng, đừng ngại gọi **115** hoặc **1800 599 913** để được hỗ trợ từ chuyên gia.

Bạn có muốn thử một trong những kỹ thuật này không? Hoặc bạn muốn nói thêm về những gì đang khiến bạn cảm thấy như vậy?"""
    
    state["answer"] = message
    state["skip_translation"] = True
    state["done"] = False
    state["crisis_stage"] = 3
    state["crisis_context_retrieved"] = True
    
    logger.info(f"[CRISIS SUPPORT] Contextual support provided.")
    
    return state


# ============================================================================
# STAGE 3C: GENTLE PERSISTENCE (Declining Help)
# ============================================================================

async def crisis_gentle_persistence_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 3C: Gentle persistence for resistant users
    
    Triggers: User declining/defensive
    Features: Validation, respect boundaries, gentle reminder
    """
    empathy = state.get("empathy_preamble_vi", "")
    
    logger.info(f"[CRISIS PERSISTENCE] User declining help. Gentle persistence approach.")
    
    message = f"""{empathy}

Tôi hiểu bạn có thể chưa sẵn sàng nói về điều này, và đó là quyền của bạn.

Tôi chỉ muốn bạn biết:
• Những cảm xúc bạn đang có là có thật và quan trọng
• Bạn không cần phải đối mặt với chúng một mình
• Có những người được đào tạo để giúp đỡ, không phán xét: **1800 599 913**

Nếu bạn thay đổi ý định, tôi vẫn ở đây để lắng nghe.

Bạn có muốn nói về điều gì khác không? Hoặc tôi có thể giúp bạn tìm thông tin về cách đối phó với cảm xúc khó khăn?"""
    
    state["answer"] = message
    state["skip_translation"] = True
    state["done"] = False
    state["crisis_stage"] = 2
    state["crisis_response_count"] = state.get("crisis_response_count", 0) + 1
    state["crisis_de_escalation_attempted"] = True
    
    return state


# ============================================================================
# STAGE 3D: TRANSITION TO NORMAL (De-escalated)
# ============================================================================

async def crisis_to_normal_transition_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    STAGE 3D: Transition from crisis to normal flow
    
    Triggers: User de-escalated/calmer
    Features: Acknowledge improvement, gentle reminder, enable normal flow
    """
    empathy = state.get("empathy_preamble_vi", "")
    
    logger.info(f"[CRISIS TRANSITION] User de-escalated. Transitioning to normal flow.")
    
    message = f"""{empathy}

Tôi rất vui vì bạn đang cảm thấy ổn định hơn.

Để đảm bảo an toàn, tôi muốn nhắc bạn:
• Nếu bất cứ lúc nào cảm giác trở lại, hãy gọi **115** hoặc **1800 599 913**
• Số này luôn sẵn sàng 24/7, không cần ngại ngùng

Bây giờ, bạn muốn nói về điều gì? Tôi có thể giúp bạn với:
• Cách đối phó với căng thẳng
• Kỹ thuật thư giãn
• Thông tin về các rối loạn tâm lý
• Hoặc bất cứ điều gì bạn cần"""
    
    state["answer"] = message
    state["skip_translation"] = True
    state["done"] = False
    state["crisis_level"] = "moderate"  # Downgrade from "high"
    state["crisis_stage"] = None  # Exit crisis mode
    state["requires_safety_monitoring"] = True  # Enable monitoring
    
    logger.info(f"[CRISIS TRANSITION] Transitioned to moderate monitoring mode.")
    
    return state


# ============================================================================
# LEGACY NODE (for backward compatibility)
# ============================================================================

async def crisis_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LEGACY: Old crisis response node
    Redirects to crisis_immediate_response_node
    """
    logger.warning("[CRISIS RESPONSE] Legacy node called. Redirecting to immediate response.")
    return await crisis_immediate_response_node(state)


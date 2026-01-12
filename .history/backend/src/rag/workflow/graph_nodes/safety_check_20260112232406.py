"""
Safety Check Node
Node wrapper for context-aware safety screening
"""
from typing import Dict, Any
import logging

from src.rag.llm.answer_nodes.safety_check import process_safety_check
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load crisis response template
response_templates = load_prompts("response_templates.yaml")
crisis_response = response_templates.get("crisis_response", "")


async def safety_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Check if question indicates high-risk situation requiring crisis intervention.
    
    UPGRADED: Now context-aware with conversation history to detect subtle/progressive risk signals.
    
    Args:
        state: State dict with question, query_type, conversation context
    
    Returns:
        Updated state with is_high_risk flag and optional crisis response override
    """
    # Extract parameters from state
    question = state["question"]
    query_type = state.get("query_type")
    should_enhance = state.get("should_enhance_query", False)
    buffer = state.get("conversation_buffer", [])
    summary = state.get("summary_context", "")
    
    logger.info(f"[SAFETY CHECK NODE] Processing question: {question[:100]}...")
    logger.info(f"[SAFETY CHECK NODE] Buffer has {len(buffer)} messages")
    
    # === FORMAT HISTORY FROM BUFFER ===
    # Take last N messages from conversation_buffer
    N = 8  # Last 8 messages = 4 turns of conversation
    recent = buffer[-N:] if len(buffer) > N else buffer
    
    def _get_role(m):
        """Extract role from message (flexible for different structures)"""
        if hasattr(m, "type"):
            return m.type
        elif isinstance(m, dict):
            return m.get("type", "unknown")
        return "unknown"
    
    def _get_content(m):
        """Extract content from message (flexible for different structures)"""
        if hasattr(m, "content"):
            return m.content
        elif isinstance(m, dict):
            return m.get("content", "")
        return str(m)
    
    history_lines = []
    for msg in recent:
        role = _get_role(msg)
        content = _get_content(msg)
        if content:  # Only add non-empty messages
            history_lines.append(f"{role}: {content}")
    
    history_str = "\n".join(history_lines).strip() if history_lines else "No previous conversation."
    
    logger.info(f"[SAFETY CHECK NODE] Formatted history: {len(recent)} messages, {len(history_str)} chars")
    logger.debug(f"[SAFETY CHECK NODE] History preview: {history_str[:200]}...")
    
    # === CALL LOGIC FUNCTION ===
    try:
        result = await process_safety_check(
            question=question,
            history=history_str,
            summary_context=summary,
            query_type=query_type,
            should_enhance=should_enhance,
            conversation_buffer=buffer
        )
        
        logger.info(f"[SAFETY CHECK NODE] Result: {result}")
        
        # Parse result
        parsed = result.get("parsed_output") or result.get("output") or result
        is_high_risk = result.get("is_high_risk", False)
        
        classification = None
        reason = ""
        confidence = "medium"
        indicators = []
        
        if isinstance(parsed, dict):
            classification = parsed.get("classification")
            reason = parsed.get("reason", "")
            confidence = parsed.get("confidence", "medium")
            indicators = parsed.get("indicators", [])
        
        # === FALLBACK if parse failed ===
        if classification not in ("high_risk", "safe"):
            logger.warning(f"[SAFETY CHECK NODE] Invalid classification: {classification}. Using keyword fallback.")
            text = (question or "").lower()
            
            # High-risk keywords (Vietnamese + English)
            risk_keywords = [
                "tự tử", "tự sát", "tự hại", "muốn chết", "không muốn sống",
                "kết liễu", "end it all", "kill myself", "suicide",
                "cắt tay", "overdose", "uống thuốc", "nhảy lầu",
                "giết người", "làm hại", "đâm", "dao", "harm others"
            ]
            
            if any(k in text for k in risk_keywords):
                classification = "high_risk"
                is_high_risk = True
                reason = "Keyword-based fallback detection"
            else:
                classification = "safe"
                is_high_risk = False
                reason = "No high-risk keywords found"
        
        # === CLASSIFY CRISIS LEVEL ===
        crisis_level = None
        
        if classification == "high_risk" or is_high_risk:
            # Determine crisis level based on indicators
            # "critical" - immediate danger (plan + means + intent)
            # "high" - suicidal ideation or self-harm urges (no immediate action)
            
            indicator_set = set([ind.lower() for ind in indicators])
            
            # Critical: Has plan + means + intent OR active harm
            critical_combos = [
                {"plan", "means", "intent"},
                {"plan", "means"},
                {"immediate", "action"},
                {"active", "harm"}
            ]
            
            is_critical = any(
                combo.issubset(indicator_set) for combo in critical_combos
            )
            
            # Check for critical keywords in question
            critical_keywords = [
                "đã chuẩn bị", "đang cầm", "sắp", "ngay bây giờ", "hiện tại",
                "ready to", "about to", "right now", "have the"
            ]
            
            question_lower = question.lower()
            has_critical_keyword = any(k in question_lower for k in critical_keywords)
            
            if is_critical or has_critical_keyword:
                crisis_level = "critical"
                logger.critical(f"[SAFETY CHECK] 🔴 CRITICAL CRISIS: Immediate danger detected")
            else:
                crisis_level = "high"
                logger.warning(f"[SAFETY CHECK] 🟠 HIGH CRISIS: Significant risk detected")
        
        # === MAP TO STATE FLAGS ===
        if classification == "high_risk" or is_high_risk:
            state["is_high_risk"] = True
            state["response_override"] = crisis_response  # Override with crisis response
            state["risk_indicators"] = indicators  # Store detected indicators
            state["crisis_level"] = crisis_level  # NEW: Store crisis level
            state["crisis_indicators"] = indicators  # NEW: Store for crisis nodes
            
            # Initialize crisis tracking if first detection
            if state.get("crisis_response_count") is None:
                state["crisis_response_count"] = 0
            
            logger.critical(f"[SAFETY CHECK NODE] 🚨 HIGH RISK DETECTED: {reason}")
            if indicators:
                logger.critical(f"[SAFETY CHECK NODE] Indicators: {', '.join(indicators)}")
            logger.critical(f"[SAFETY CHECK NODE] Crisis Level: {crisis_level}")
        else:  # safe
            state["is_high_risk"] = False
            # No response override - continue normal flow
            logger.info(f"[SAFETY CHECK NODE] ✅ SAFE: {reason}")
        
        # Store metadata
        state["safety_reason"] = reason
        state["safety_confidence"] = confidence
        state["safety_classification"] = classification
        
    except Exception as e:
        logger.error(f"[SAFETY CHECK NODE] Error: {e}", exc_info=True)
        # Safe fallback - don't block user
        state["is_high_risk"] = False
        state["safety_reason"] = f"Error in safety check: {str(e)}"
    
    return state

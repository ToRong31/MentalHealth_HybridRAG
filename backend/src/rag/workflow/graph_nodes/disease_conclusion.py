"""
Disease Conclusion Node
Concludes diagnosis and asks if user wants treatment guidance
"""
import logging
from typing import Dict, Any

from ..state import KGState

logger = logging.getLogger(__name__)


async def disease_conclusion_node(state: KGState) -> KGState:
    """
    Inform user about detected disease and ask about treatment
    
    Args:
        state: KGState with detected_disease, diagnostic_confidence, diagnostic_reasoning
    
    Returns:
        Updated state with answer and awaiting_treatment_confirmation flag
    """
    detected_disease = state.get("detected_disease", "")
    confidence = state.get("diagnostic_confidence", 0.0)
    reasoning = state.get("diagnostic_reasoning", "")
    language = state.get("user_language", "vi")
    
    logger.info(f"📋 Concluding disease: '{detected_disease}' with confidence {confidence:.2f}")
    
    if language == "vi" or language == "vn":
        conclusion = f"""Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn có thể đang gặp phải: **{detected_disease}**

**Lý do:** {reasoning}

Bạn có muốn tôi hướng dẫn cách điều trị và giải quyết vấn đề này không?"""
    else:
        conclusion = f"""Based on the symptoms you described, I believe you may be experiencing: **{detected_disease}**

**Reasoning:** {reasoning}

Would you like me to guide you on treatment and solutions for this condition?"""
    
    logger.info(f"✅ Disease conclusion generated for: '{detected_disease}'")
    
    state["answer"] = conclusion
    state["awaiting_treatment_confirmation"] = True
    
    return state

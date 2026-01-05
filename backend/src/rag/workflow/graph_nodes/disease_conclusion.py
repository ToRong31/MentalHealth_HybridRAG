"""
Disease Conclusion Node
Analyzes symptoms and concludes diagnosis
"""
import logging
import asyncio
from typing import Dict, Any, List

from ..state import KGState
from src.rag.llm.answer_nodes.disease_conclusion import analyze_disease

logger = logging.getLogger(__name__)


def verify_diseases_with_context(
    diagnostic_diseases: List[str],
    diagnostic_chunks: str,
    rewritten_query: str,
    slots: Dict[str, Any],
    conversation_buffer: list,
    summary_context: str
) -> tuple[str, float, str, str, str, str]:
    """
    Verify which disease from retrieved list matches the conversation context
    
    Args:
        diagnostic_diseases: List of diseases from retrieval
        diagnostic_chunks: Retrieved diagnostic chunks with diseases
        rewritten_query: User's query
        slots: Extracted slots
        conversation_buffer: Conversation history
        summary_context: Summary context
    
    Returns:
        Tuple of (selected_disease, confidence, reasoning, description, symptoms, causes)
    """
    # Use LLM to analyze conversation and select most appropriate disease
    detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes = analyze_disease(
        diagnostic_chunks,
        rewritten_query,
        slots,
        conversation_buffer,
        summary_context
    )
    
    # Verify that LLM's disease is in the retrieved list
    if detected_disease:
        # Try exact match first
        if detected_disease in diagnostic_diseases:
            logger.info(f"✅ LLM selected disease '{detected_disease}' matches retrieved diseases")
            return detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes
        
        # Try partial match (in case of formatting differences)
        for disease in diagnostic_diseases:
            if detected_disease.lower() in disease.lower() or disease.lower() in detected_disease.lower():
                logger.info(f"✅ LLM disease '{detected_disease}' matched to '{disease}'")
                return disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes
        
        # LLM picked a disease not in retrieval - use top retrieved disease instead
        logger.warning(f"⚠️ LLM selected '{detected_disease}' not in retrieval list. Using top retrieved disease.")
    
    # Fallback to top retrieved disease if LLM didn't find valid disease
    if diagnostic_diseases:
        return diagnostic_diseases[0], 0.7, f"Selected from retrieved diseases: {', '.join(diagnostic_diseases)}", "", "", ""
    
    return "", 0.0, "No disease detected", "", "", ""

logger = logging.getLogger(__name__)


async def disease_conclusion_node(state: KGState) -> KGState:
    """
    Analyze diagnostic chunks and conclude disease using LLM
    
    Args:
        state: KGState with diagnostic_chunks, rewritten_query, slots, conversation_buffer, summary_context
    
    Returns:
        Updated state with detected_disease, diagnostic_confidence, diagnostic_reasoning, answer
    """
    diagnostic_chunks = state.get("diagnostic_chunks", "")
    diagnostic_diseases = state.get("diagnostic_diseases", [])
    diagnostic_disease_details = state.get("diagnostic_disease_details", [])
    rewritten_query = state.get("rewritten_query", state.get("question", ""))
    slots = state.get("slots", {})
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    language = state.get("user_language", "vi")
    
    logger.info(f"📋 Verifying diseases from retrieval with conversation context")
    logger.info(f"🔍 Retrieved diseases: {diagnostic_diseases}")
    
    if not diagnostic_chunks or not diagnostic_diseases:
        logger.warning("⚠️ No diagnostic chunks or diseases available")
        state["answer"] = "Xin lỗi, tôi không tìm thấy thông tin chẩn đoán phù hợp." if language == "vi" else "Sorry, I couldn't find relevant diagnostic information."
        return state
    
    try:
        # Use LLM to verify and select disease based on conversation context
        loop = asyncio.get_event_loop()
        detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes = await loop.run_in_executor(
            None,
            verify_diseases_with_context,
            diagnostic_diseases,
            diagnostic_chunks,
            rewritten_query,
            slots,
            conversation_buffer,
            summary_context
        )
        
        if detected_disease:
            logger.info(f"✅ Disease conclusion: disease='{detected_disease}', confidence={confidence:.2f}")
            
            # Save analysis results
            state["detected_disease"] = detected_disease
            state["diagnostic_confidence"] = confidence
            state["diagnostic_reasoning"] = reasoning
            state["disease_description"] = disease_description
            state["disease_symptoms"] = disease_symptoms
            state["disease_causes"] = disease_causes
            
            # Add to disease_detected list if confidence is high enough (>= 0.6)
            if confidence >= 0.8:
                disease_list = state.get("disease_detected", [])
                if disease_list is None:
                    disease_list = []
                if detected_disease not in disease_list:
                    disease_list.append(detected_disease)
                    state["disease_detected"] = disease_list
                    logger.info(f"✅ Disease '{detected_disease}' added to disease_detected list (confidence: {confidence:.2f})")
                else:
                    logger.info(f"ℹ️ Disease '{detected_disease}' already in disease_detected list")
            else:
                logger.info(f"ℹ️ Disease '{detected_disease}' confidence too low ({confidence:.2f}) to add to disease_detected")
            
            # Generate conclusion message with disease information
            if language == "vi" or language == "vn":
                # Build disease info section
                disease_info = ""
                if disease_description:
                    disease_info += f"\n\n**{detected_disease} là gì?**\n{disease_description}"
                if disease_symptoms:
                    disease_info += f"\n\n**Triệu chứng chính:**\n{disease_symptoms}"
                if disease_causes:
                    disease_info += f"\n\n**Nguyên nhân:**\n{disease_causes}"
                
                conclusion = f"""Dựa trên các triệu chứng bạn mô tả, tôi nhận thấy bạn **có dấu hiệu có thể mắc** {detected_disease}.

**Phân tích triệu chứng của bạn:** {reasoning}{disease_info}

**Lưu ý:** Đây chỉ là đánh giá sơ bộ dựa trên thông tin bạn cung cấp, không thay thế cho chẩn đoán y tế chuyên nghiệp.

Bạn có muốn tôi gợi ý cho bạn một số cách chữa trị không?"""
            else:
                # Build disease info section
                disease_info = ""
                if disease_description:
                    disease_info += f"\n\n**What is {detected_disease}?**\n{disease_description}"
                if disease_symptoms:
                    disease_info += f"\n\n**Main Symptoms:**\n{disease_symptoms}"
                if disease_causes:
                    disease_info += f"\n\n**Causes:**\n{disease_causes}"
                
                conclusion = f"""Based on the symptoms you described, I observe that you **may show signs of possibly having** {detected_disease}.

**Analysis of your symptoms:** {reasoning}{disease_info}

**Note:** This is only a preliminary assessment based on the information you provided, and does not replace professional medical diagnosis.

Would you like me to suggest some treatment options?"""
            
            state["answer"] = conclusion
            state["awaiting_treatment_confirmation"] = True
        else:
            logger.warning("⚠️ No disease confirmed from verification")
            state["answer"] = "Xin lỗi, tôi không thể xác định bệnh từ các triệu chứng." if language == "vi" else "Sorry, I couldn't identify a condition from the symptoms."
        
    except Exception as e:
        logger.error(f"❌ Error in disease conclusion: {e}", exc_info=True)
        state["answer"] = "Xin lỗi, đã xảy ra lỗi trong quá trình phân tích." if language == "vi" else "Sorry, an error occurred during analysis."
    
    return state

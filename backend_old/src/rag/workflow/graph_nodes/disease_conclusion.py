"""
Disease Conclusion Node
Analyzes symptoms and concludes diagnosis
"""
import logging
import asyncio
from typing import Dict, Any, List

from ..state import KGState
from src.rag.llm.answer_nodes.disease_conclusion import analyze_disease, evaluate_all_diseases
from src.rag.utils.disease_translation import translate_disease_name

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
    Evaluate ALL diseases from retrieval and return the best match with highest confidence
    
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
    # Use LLM to evaluate ALL diseases and pick the best match
    detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes = evaluate_all_diseases(
        diagnostic_diseases,
        diagnostic_chunks,
        rewritten_query,
        slots,
        conversation_buffer,
        summary_context
    )
    
    logger.info(f"🎯 LLM evaluated all diseases and selected: '{detected_disease}' with confidence={confidence:.2f}")
    
    return detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes

logger = logging.getLogger(__name__)


async def disease_conclusion_node(state: KGState) -> KGState:
    """
    Analyze diagnostic chunks and conclude disease using LLM.
    
    This node receives:
    - diagnostic_chunks: Retrieved content (based on pure symptoms)
    - assessment_category: Assessment context (for conclusion)
    - screening_result: Screening context (for conclusion)
    - slots: Raw symptom data
    
    Args:
        state: KGState with diagnostic_chunks, assessment context, screening context
    
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
            
            # Extract chunks related to detected disease for LLM to generate conclusion
            detected_disease_chunk = ""
            if diagnostic_chunks and detected_disease:
                # Try to find chunks mentioning the detected disease
                chunks_list = diagnostic_chunks.split("\n---\n")
                relevant_chunks = [chunk for chunk in chunks_list if detected_disease.lower() in chunk.lower()]
                if relevant_chunks:
                    detected_disease_chunk = "\n---\n".join(relevant_chunks[:3])  # Top 3 relevant chunks
                else:
                    # Fallback to first few chunks if no exact match
                    detected_disease_chunk = "\n---\n".join(chunks_list[:3])
            
            # Save analysis results
            state["detected_disease"] = detected_disease
            state["diagnostic_confidence"] = confidence
            state["diagnostic_reasoning"] = reasoning
            state["disease_description"] = disease_description
            state["disease_symptoms"] = disease_symptoms
            state["disease_causes"] = disease_causes
            state["detected_disease_chunk"] = detected_disease_chunk  # Save relevant chunks
            
            # Only conclude disease if confidence > 0.75
            if confidence > 0.75:
                # Translate disease name to Vietnamese if needed
                disease_name_display = detected_disease
                if language == "vi" or language == "vn":
                    disease_name_display = translate_disease_name(detected_disease)
                    logger.info(f"📝 Translated disease name: '{detected_disease}' -> '{disease_name_display}'")
                
                # Add to disease_detected list
                disease_list = state.get("disease_detected", [])
                if disease_list is None:
                    disease_list = []
                if detected_disease not in disease_list:
                    disease_list.append(detected_disease)
                    state["disease_detected"] = disease_list
                    logger.info(f"✅ Disease '{detected_disease}' added to disease_detected list (confidence: {confidence:.2f})")
                else:
                    logger.info(f"ℹ️ Disease '{detected_disease}' already in disease_detected list")
                
                # Generate conclusion message using LLM
                if language == "vi" or language == "vn":
                    disease_name_display = translate_disease_name(detected_disease)
                    logger.info(f"📝 Translated disease name: '{detected_disease}' -> '{disease_name_display}'")
                else:
                    disease_name_display = detected_disease
                
                # Extract brief user symptoms from reasoning
                brief_symptoms = ""
                if reasoning and len(reasoning) > 50:
                    import re
                    symptom_match = re.search(r'reports?:?\s*(.+?)(?:\.|This matches|Duration|Among)', reasoning, re.IGNORECASE | re.DOTALL)
                    if symptom_match:
                        brief_symptoms = symptom_match.group(1).strip()[:300]
                
                # Call LLM to generate personalized conclusion
                try:
                    from src.rag.prompts.loader import load_prompts
                    from src.rag.llm.llm_gemini import llm
                    
                    prompt_templates = load_prompts("conclusion_diagnostic.yaml")
                    system_prompt = prompt_templates.get("system", "")
                    user_prompt_template = prompt_templates.get("user", "")
                    
                    user_prompt = user_prompt_template.format(
                        disease_name=disease_name_display,
                        disease_chunks=detected_disease_chunk[:1500],  # Limit chunk size
                        disease_description=disease_description or "No description available",
                        user_symptoms=brief_symptoms or disease_symptoms[:300] if disease_symptoms else "Various symptoms",
                        reasoning=reasoning[:500] if reasoning else "",  # Brief reasoning
                        language="tiếng Việt" if language in ["vi", "vn"] else "English"
                    )
                    
                    full_prompt = f"{system_prompt}\n\n{user_prompt}"
                    
                    logger.info("🤖 Calling LLM to generate conclusion message...")
                    conclusion = llm.invoke(full_prompt, max_retries=2)
                    
                    # Clean up response
                    conclusion = conclusion.strip()
                    if conclusion.startswith("```"):
                        conclusion = conclusion.split("```", 2)[1] if "```" in conclusion else conclusion
                    
                    logger.info(f"✅ LLM generated conclusion (length: {len(conclusion)} chars)")
                    
                except Exception as e:
                    logger.error(f"⚠️ Error generating LLM conclusion: {e}, using fallback template")
                    # Fallback to simple template if LLM fails
                    if language == "vi" or language == "vn":
                        conclusion = f"""**Tình trạng của bạn: {disease_name_display}**

{disease_description if disease_description else f"Bạn có dấu hiệu của {disease_name_display}."}

Đây là một vấn đề y tế có thể điều trị. Việc hiểu rằng đây là vấn đề y tế sẽ giúp bạn tập trung vào giải pháp.

**Lưu ý:** Đây là đánh giá sơ bộ, không thay thế chẩn đoán y tế chuyên nghiệp.

Bạn có muốn tôi gợi ý một số cách chữa trị không?"""
                    else:
                        conclusion = f"""**Your Condition: {detected_disease}**

{disease_description if disease_description else f"You show signs of {detected_disease}."}

This is a treatable medical condition. Understanding this is a medical issue will help you focus on solutions.

**Note:** This is a preliminary assessment, not a replacement for professional diagnosis.

Would you like me to suggest some treatment options?"""
                
                state["answer"] = conclusion
                state["awaiting_treatment_confirmation"] = True
            else:
                # Confidence <= 0.75: fallback to graph retrieve
                logger.info(f"⚠️ Confidence too low ({confidence:.2f} <= 0.75), will fallback to graph retrieve")
                state["answer"] = ""  # Clear answer to trigger graph retrieve
        else:
            logger.warning("⚠️ No disease confirmed from verification")
            state["answer"] = "Xin lỗi, tôi không thể xác định bệnh từ các triệu chứng." if language == "vi" else "Sorry, I couldn't identify a condition from the symptoms."
        
    except Exception as e:
        logger.error(f"❌ Error in disease conclusion: {e}", exc_info=True)
        state["answer"] = "Xin lỗi, đã xảy ra lỗi trong quá trình phân tích." if language == "vi" else "Sorry, an error occurred during analysis."
    
    return state

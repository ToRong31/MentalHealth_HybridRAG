"""
Answer with Treatment Node
Generates treatment answer using retrieved treatment chunks
"""
import json
import logging
from typing import Dict, Any

from ..state import KGState
from src.rag.llm.llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)


async def answer_with_treatment_node(state: KGState) -> KGState:
    """
    Generate treatment guidance answer
    
    Args:
        state: KGState with detected_disease, treatment_chunks, slots, conversation_buffer, summary_context
    
    Returns:
        Updated state with answer
    """
    detected_disease = state.get("detected_disease", "")
    treatment_chunks = state.get("treatment_chunks", [])
    slots = state.get("slots", {})
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    language = state.get("user_language", "vi")
    
    logger.info(f"💬 Generating treatment answer for disease: '{detected_disease}'")
    
    if not treatment_chunks:
        logger.warning("⚠️ No treatment chunks available")
        error_msg = (
            "Xin lỗi, tôi không tìm thấy hướng dẫn điều trị cụ thể cho tình trạng này." 
            if language in ["vi", "vn"] 
            else "Sorry, I couldn't find specific treatment guidance for this condition."
        )
        state["answer"] = error_msg
        return state
    
    try:
        # Load treatment answer prompt
        prompt_templates = load_prompts("treatment_answer_prompt.yaml")
        system_prompt = prompt_templates.get("system", "")
        user_prompt_template = prompt_templates.get("user", "")
        
        # Format conversation history
        conversation_history = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
            for msg in conversation_buffer[-5:]
        ]) if conversation_buffer else "Không có lịch sử hội thoại"
        
        # Format treatment chunks
        treatment_context = "\n\n".join([
            f"Hướng dẫn {i+1}:\n{chunk}" 
            for i, chunk in enumerate(treatment_chunks)
        ])
        
        # Format user prompt
        user_prompt = user_prompt_template.format(
            disease=detected_disease,
            slots=json.dumps(slots, ensure_ascii=False, indent=2),
            conversation_history=conversation_history,
            summary=summary_context or "Không có tóm tắt",
            treatment_chunks=treatment_context,
            language=language
        )
        
        # Call LLM for treatment answer
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        import asyncio
        loop = asyncio.get_event_loop()
        answer_content = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        logger.info(f"✅ Generated treatment answer (length: {len(answer_content)})")
        
        state["answer"] = answer_content
        
    except Exception as e:
        logger.error(f"❌ Error generating treatment answer: {e}", exc_info=True)
        error_msg = (
            "Xin lỗi, đã có lỗi khi tạo hướng dẫn điều trị. Vui lòng thử lại." 
            if language in ["vi", "vn"] 
            else "Sorry, there was an error generating treatment guidance. Please try again."
        )
        state["answer"] = error_msg
    
    return state

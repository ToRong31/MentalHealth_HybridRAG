"""
Answer with Dense Node
Sinh câu trả lời dựa trên document context từ dense retrieval
"""
import asyncio
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Templates will be loaded lazily
system_instructions_dense = None
user_template_dense = None
fallback_answer = None


async def generate_answer_with_dense(
    question: str,
    dense_context: str = "",
    user_language: str = "en",
    original_question: str = None,
    slots: dict = None,
    follow_up_questions: list = None,
    relevant_missing_slots: list = None,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> str:
    """
    Generate answer based on dense retrieval context.
    
    """
    # Lazy load templates if not loaded yet
    global system_instructions_dense, user_template_dense, fallback_answer
    if user_template_dense is None:
        try:
            response_templates_dense = await load_prompts("answer_dense_promt_vie.yaml")
            system_instructions_dense = response_templates_dense.get("system_instructions", "")
            user_template_dense = response_templates_dense.get("user_template", "")
            
            if not user_template_dense:
                raise ValueError("Missing user_template in answer_dense_promt.yaml")
            logger.info("Successfully loaded answer_dense_promt.yaml")
        except Exception as e:
            logger.error(f"Failed to load answer_dense_promt.yaml: {e}")
            system_instructions_dense = ""
            user_template_dense = ""
    
    if fallback_answer is None:
        try:
            response_templates = await load_prompts("response_templates.yaml")
            fallback_answer = response_templates.get("fallback_answer", "")
        except Exception as e:
            logger.error(f"Failed to load fallback answer: {e}")
            fallback_answer = """I'm having technical difficulties. Could you share more about your situation?"""
    Args:
        question: User question (may be translated)
        dense_context: Context from dense retrieval
        user_language: User's language (vi/en)
        original_question: Original question if translated
        slots: User's personal context slots
        follow_up_questions: Generated follow-up questions
        relevant_missing_slots: Relevant missing slot information
    
    Returns:
        Generated answer string
    """
    if slots is None:
        slots = {}
    if follow_up_questions is None:
        follow_up_questions = []
    if relevant_missing_slots is None:
        relevant_missing_slots = []
    if conversation_buffer is None:
        conversation_buffer = []
    
    # Get question (use original for Vietnamese)
    q = original_question if (user_language == "vi" and original_question) else question
    
    try:
        # Build slot context
        slot_info = ""
        if slots:
            from src.rag.utils.slots import build_slot_context
            slot_info = build_slot_context(slots)
        
        # Build conversation context (last 3 pairs + summary)
        conversation_context = ""
        if summary_context or conversation_buffer:
            from src.rag.utils.memory import format_buffer_for_context, format_summary_context
            
            context_parts_conv = []
            if summary_context:
                context_parts_conv.append(f"Previous conversation summary: {format_summary_context(summary_context)}")
            
            # Use only last 3 buffer pairs
            recent_buffer = conversation_buffer[-3:] if conversation_buffer else []
            if recent_buffer:
                context_parts_conv.append(f"Recent conversation:\n{format_buffer_for_context(recent_buffer)}")
            
            if context_parts_conv:
                conversation_context = "\n".join(context_parts_conv)
                logger.info(f"📚 Added conversation context: {len(recent_buffer)} recent pairs + summary")
        
        # Build combined context
        context_parts = []
        
        if dense_context:
            context_parts.append(f"Knowledge from documents:\n{dense_context}")
        else:
            context_parts.append("No specific knowledge available.")
        
        if slot_info:
            context_parts.append(f"\nUser's personal context:\n{slot_info}")
        
        if conversation_context:
            context_parts.append(f"\nConversation context:\n{conversation_context}")
        
        combined_context = "\n".join(context_parts)
        
        # Build full prompt
        user_message = user_template_dense.replace("{{PATIENT_INPUT}}", q).replace(
            "{{DOCTOR_DIALOGUE}}",
            combined_context
        )
        
        # Add follow-up questions instruction if available
        if follow_up_questions and relevant_missing_slots:
            user_message += f"\n\nIMPORTANT: The user's message suggests they might benefit from sharing more about: {', '.join(relevant_missing_slots)}. "
            user_message += "After providing your main response, naturally and empathetically ask these relevant follow-up questions to better understand their situation:\n"
            for question_text in follow_up_questions:
                user_message += f"- {question_text}\n"
            user_message += "\nIntegrate these questions naturally into your response, not as a separate list. Only ask if it feels appropriate given the context."
        
        full_prompt = f"{system_instructions_dense}\n\n{user_message}"

        # Generate answer
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        return answer
        
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return fallback_answer

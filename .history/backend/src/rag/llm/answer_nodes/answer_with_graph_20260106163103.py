"""
Answer with Graph Node
Sinh câu trả lời dựa trên graph context
Enhanced với conversation buffer và summary context
"""
import asyncio
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts
from src.rag.utils.memory import format_buffer_for_context, format_summary_context

logger = logging.getLogger(__name__)

# Fallback answer will be loaded lazily
fallback_answer = None


async def generate_answer_with_graph(
    question: str,
    graph_context: str = "",
    user_language: str = "en",
    original_question: str = None,
    slots: dict = None,
    follow_up_questions: list = None,
    relevant_missing_slots: list = None,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> str:
    """
    Generate answer based on graph context with conversation memory.
    
    Args:
        question: User question (may be translated)
        graph_context: Context from graph retrieval
        user_language: User's language (vi/en)
        original_question: Original question if translated
        slots: User's personal context slots
        follow_up_questions: Generated follow-up questions
        relevant_missing_slots: Relevant missing slot information
        conversation_buffer: Recent conversation history
        summary_context: Summary of older conversation
    
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
    
    # Lazy load fallback answer if not loaded yet
    global fallback_answer
    if fallback_answer is None:
        try:
            response_templates = await load_prompts("response_templates.yaml")
            fallback_answer = response_templates.get("fallback_answer", "")
        except Exception as e:
            logger.error(f"Failed to load fallback answer: {e}")
            fallback_answer = """I'm having technical difficulties. Could you share more about your situation?"""
    
    # Load appropriate prompt based on user language
    if user_language == "vi":
        try:
            answer_prompt_data = await load_prompts("answer_nodes_prompt_vie.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
            
            if not system_instructions or not user_template:
                raise ValueError("Missing system_instructions or user_template")
            
            logger.info("Successfully loaded Vietnamese therapist prompt")
        except Exception as e:
            logger.warning(f"Failed to load Vietnamese prompt: {e}, trying English version...")
            raise
    else:
        try:
            answer_prompt_data = await load_prompts("answer_nodes_prompt_en.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
            
            if not system_instructions or not user_template:
                raise ValueError("Missing system_instructions or user_template")
            
            logger.info("Successfully loaded English therapist prompt")
        except Exception as e:
            logger.error(f"Failed to load English prompt: {e}")
            raise RuntimeError(f"Cannot load any therapist prompt files: {e}")
    
    # Get question (use original for Vietnamese)
    q = original_question if (user_language == "vi" and original_question) else question
    
    try:
        # Build slot context
        slot_info = ""
        if slots:
            from src.rag.utils.slots import build_slot_context
            slot_info = build_slot_context(slots)
        
        # Format conversation memory
        summary_text = format_summary_context(summary_context)
        buffer_text = format_buffer_for_context(conversation_buffer)
        
        # Build combined context
        context_parts = []
        
        if graph_context:
            context_parts.append(f"Knowledge from graph:\n{graph_context}")
        else:
            context_parts.append("No specific knowledge available.")
        
        if slot_info:
            context_parts.append(f"\nUser's personal context:\n{slot_info}")
        
        if summary_text:
            context_parts.append(f"\nPrevious conversation summary:\n{summary_text}")
        
        if buffer_text:
            context_parts.append(f"\nRecent conversation history:\n{buffer_text}")
        
        combined_context = "\n".join(context_parts)
        
        # Build full prompt
        user_message = user_template.replace("{{QUESTION}}", q).replace(
            "{{GRAPH_CONTEXT}}",
            combined_context
        )
        
        # Add follow-up questions instruction if available
        if follow_up_questions and relevant_missing_slots:
            user_message += f"\n\nIMPORTANT: The user's message suggests they might benefit from sharing more about: {', '.join(relevant_missing_slots)}. "
            user_message += "After providing your main response, naturally and empathetically ask these relevant follow-up questions to better understand their situation:\n"
            for question_text in follow_up_questions:
                user_message += f"- {question_text}\n"
            user_message += "\nIntegrate these questions naturally into your response, not as a separate list. Only ask if it feels appropriate given the context."
        
        full_prompt = f"{system_instructions}\n\n{user_message}"
        
        # Generate answer
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        return answer
        
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return fallback_answer

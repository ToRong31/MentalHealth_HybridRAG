"""
Answer with Graph Node
Sinh câu trả lời dựa trên graph context
"""
import asyncio
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load fallback answer
try:
    response_templates = load_prompts("response_templates.yaml")
    fallback_answer = response_templates.get("fallback_answer", "")
except Exception as e:
    logger.error(f"Failed to load fallback answer: {e}")
    fallback_answer = """I'm having technical difficulties. Could you share more about your situation?"""


async def answer_with_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sinh câu trả lời dựa trên graph context (async version)
    
    Args:
        state: State dict với 'question' và 'graph_context'
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    # Load appropriate prompt based on user language
    if state.get("user_language") == "vi":
        try:
            answer_prompt_data = load_prompts("answer_nodes_prompt_vie.yaml")
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
            answer_prompt_data = load_prompts("answer_nodes_prompt_en.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
            
            if not system_instructions or not user_template:
                raise ValueError("Missing system_instructions or user_template")
            
            logger.info("Successfully loaded English therapist prompt")
        except Exception as e:
            logger.error(f"Failed to load English prompt: {e}")
            raise RuntimeError(f"Cannot load any therapist prompt files: {e}")
    
    # Get question (use original for Vietnamese)
    if state.get("user_language") == "vi":
        q = state.get("original_question", state["question"])
    else:
        q = state["question"]
    
    # Use combined_context if available (from parallel retrieval), otherwise use graph_context
    graph_context = state.get("combined_context") or state.get("graph_context", "")
    
    # Get slot information for personalization
    slots = state.get("slots", {})
    follow_up_questions = state.get("follow_up_questions", [])
    relevant_missing_slots = state.get("relevant_missing_slots", [])
    
    try:
        # Build slot context if available (import lazily to avoid circular import)
        slot_info = ""
        if slots:
            from src.rag.slots.utils import build_slot_context
            slot_info = build_slot_context(slots)
        
        # Build context with graph context and slot information
        combined_context = graph_context if graph_context else "No specific knowledge available."
        if slot_info:
            combined_context = f"{combined_context}\n\n{slot_info}"
        
        # Build full prompt with system instructions + user message
        user_message = user_template.replace("{{QUESTION}}", q).replace(
            "{{GRAPH_CONTEXT}}",
            combined_context
        )
        
        # Add follow-up questions instruction if available
        if follow_up_questions and relevant_missing_slots:
            user_message += f"\n\nIMPORTANT: The user's message suggests they might benefit from sharing more about: {', '.join(relevant_missing_slots)}. "
            user_message += "After providing your main response, naturally and empathetically ask these relevant follow-up questions to better understand their situation:\n"
            for question in follow_up_questions:
                user_message += f"- {question}\n"
            user_message += "\nIntegrate these questions naturally into your response, not as a separate list. Only ask if it feels appropriate given the context."
        
        # Combine system instructions with user message
        full_prompt = f"{system_instructions}\n\n{user_message}"
        
        # Generate answer with retry (run in executor)
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
    except Exception as e:
        # Fallback answer khi LLM fail
        logger.error(f"Failed to generate answer: {e}")
        answer = fallback_answer
    
    state["answer"] = answer
    state["done"] = True
    
    return state

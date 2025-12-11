"""
Not Mental Health Node
Trả về thông báo chỉ hỗ trợ mental health cho các câu hỏi không liên quan
"""
import logging
from typing import Dict, Any

from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load response templates (Vietnamese)
try:
    response_templates = load_prompts("response_templates.yaml")
    not_mental_health_response = response_templates.get("not_mental_health_response", "")
    
    if not not_mental_health_response:
        raise ValueError("Missing not_mental_health_response template")
    
    logger.info("Successfully loaded not mental health response template")
except Exception as e:
    logger.error(f"Failed to load response_templates.yaml: {e}")
    # English fallback
    not_mental_health_response = """Thank you for your question. I'm specifically trained to help with mental health concerns. Your question seems outside my expertise."""
    logger.warning("Using English fallback for not mental health response")


async def not_mental_health_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trả về thông báo chỉ hỗ trợ mental health cho các câu hỏi không liên quan (async version).
    
    Args:
        state: State dict
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    state["answer"] = not_mental_health_response
    state["skip_translation"] = True  # response already in user-facing language
    state["done"] = True
    return state

"""
Crisis Response Node
Trả về thông báo khẩn cấp cho các trường hợp high-risk
"""
import logging
from typing import Dict, Any

from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load response templates (Vietnamese)
try:
    response_templates = load_prompts("response_templates.yaml")
    crisis_response = response_templates.get("crisis_response", "")
    
    if not crisis_response:
        raise ValueError("Missing crisis_response template")
    
    logger.info("Successfully loaded crisis response template")
except Exception as e:
    logger.error(f"Failed to load response_templates.yaml: {e}")
    # English fallback
    crisis_response = """I hear that you're in a lot of pain right now. Please reach out to crisis services immediately: 988 (US), 115 (Vietnam), or your local emergency services."""
    logger.warning("Using English fallback for crisis response")


def get_crisis_response_message() -> str:
    """
    Get crisis response message for high-risk cases.
    
    Returns:
        Crisis response message string
    """
    return crisis_response

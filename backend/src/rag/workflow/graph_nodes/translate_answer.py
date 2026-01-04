"""
Translate Answer Node
Translates answer back to user's language (Vietnamese if needed)
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes  import get_translator

logger = logging.getLogger(__name__)


async def translate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch answer về ngôn ngữ của user (async version)
    
    Args:
        state: KGState with 'answer', 'user_language'
    
    Returns:
        Updated state with translated 'answer'
    """
    if state.get("skip_translation"):
        logger.info("Skipping translation step for non-graph route")
        return state

    answer = state.get("answer", "")
    user_lang = state.get("user_language", "en")
    
    logger.info(f"User language: {user_lang}")
    
    if user_lang == 'vi' and answer:
        # Dịch answer về tiếng Việt
        logger.info(f"Translating EN->VI: {answer[:50]}...")
        translator = get_translator()
        translated = translator.en_to_vi(answer)
        state["answer"] = translated
        logger.info(f"Translated to: {translated[:50]}...")
    else:
        logger.info(f"Answer stays in English")
    
    return state

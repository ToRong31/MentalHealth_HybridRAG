"""
Translate Question Node
Detects language and translates Vietnamese to English if needed
"""
import logging
from typing import Dict, Any
import time

from src.rag.llm.translator import GeminiTranslator, get_translator

logger = logging.getLogger(__name__)


async def translate_question_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dịch question sang tiếng Anh nếu cần (async version)
    Set timestamp for parallel execution tracking
    
    Args:
        state: KGState with 'question'
    
    Returns:
        Updated state with 'original_question', 'question' (translated), 'user_language', 'parallel_start_time'
    """
    question = state["question"]
    
    # Detect language
    lang = GeminiTranslator.detect_language(question)
    state["user_language"] = lang
    state["original_question"] = question
    
    logger.info(f"Detected language: {lang}")
    
    if lang == 'vi':
        # Dịch sang tiếng Anh để xử lý
        logger.info(f"Translating VI->EN: {question[:50]}...")
        translator = get_translator()
        translated = translator.vi_to_en(question)
        state["question"] = translated
        logger.info(f"Translated to: {translated[:50]}...")
    else:
        logger.info(f"Question is in English, skipping translation")
    
    # Set timestamp when parallel execution starts (safety_check + slot_filling)
    state["parallel_start_time"] = time.time()
    logger.debug(f"Set parallel_start_time: {state['parallel_start_time']}")
    
    return state

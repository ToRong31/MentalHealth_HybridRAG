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

# Load dense prompt templates
try:
    response_templates_dense = load_prompts("answer_dense_promt_vie.yaml")
    system_instructions_dense = response_templates_dense.get("system_instructions", "")
    user_template_dense = response_templates_dense.get("user_template", "")
    
    if not user_template_dense:
        raise ValueError("Missing user_template in answer_dense_promt.yaml")
    logger.info("Successfully loaded answer_dense_promt.yaml")
except Exception as e:
    logger.error(f"Failed to load answer_dense_promt.yaml: {e}")
    system_instructions_dense = ""
    user_template_dense = ""

# Load fallback answer
try:
    response_templates = load_prompts("response_templates.yaml")
    fallback_answer = response_templates.get("fallback_answer", "")
except Exception as e:
    logger.error(f"Failed to load fallback answer: {e}")
    fallback_answer = """I'm having technical difficulties. Could you share more about your situation?"""


async def generate_answer_with_dense(question: str, dense_context: str = "") -> str:
    """
    Generate answer based on dense retrieval context.
    
    Args:
        question: User question
        dense_context: Context from dense retrieval
    
    Returns:
        Generated answer string
    """
    try:
        # Build full prompt
        user_message = user_template_dense.replace("{{PATIENT_INPUT}}", question).replace(
            "{{DOCTOR_DIALOGUE}}",
            dense_context if dense_context else "No specific knowledge available."
        )
        
        full_prompt = f"{system_instructions_dense}\n\n{user_message}"
        
        # Generate answer
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        return answer
        
    except Exception as e:
        logger.error(f"Failed to generate answer: {e}")
        return fallback_answer

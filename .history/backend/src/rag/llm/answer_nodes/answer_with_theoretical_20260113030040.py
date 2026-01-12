"""
Answer with Theoretical Node
Sinh câu trả lời cho câu hỏi lý thuyết dựa trên theoretical context
"""
import asyncio
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load theoretical prompt templates
try:
    response_templates_theoretical = load_prompts("answer_with_theoretical.yaml")
    system_instructions_theoretical = response_templates_theoretical.get("system_instructions", "")
    user_template_theoretical = response_templates_theoretical.get("user_template", "")
    
    if not user_template_theoretical:
        raise ValueError("Missing user_template in answer_with_theoretical.yaml")
    logger.info("Successfully loaded answer_with_theoretical.yaml")
except Exception as e:
    logger.error(f"Failed to load answer_with_theoretical.yaml: {e}")
    system_instructions_theoretical = ""
    user_template_theoretical = ""

# Load fallback answer
try:
    response_templates = load_prompts("response_templates.yaml")
    fallback_answer = response_templates.get("fallback_answer", "")
except Exception as e:
    logger.error(f"Failed to load fallback answer: {e}")
    fallback_answer = """Xin lỗi, tôi đang gặp vấn đề kỹ thuật. Bạn có thể chia sẻ thêm về tình huống của bạn không?"""


def fix_bullet_formatting(text: str) -> str:
    """
    Ensure bullet points ▸ are always on new lines.
    
    Fixes patterns like:
    - "▸ Item1 ▸ Item2" → "▸ Item1\n▸ Item2"
    - "text▸ Item" → "text\n▸ Item"
    - "chính: ▸ Item" → "chính:\n▸ Item"
    - "Item. ▸ Next" → "Item.\n▸ Next"
    
    Args:
        text: Input text that may have ▸ not on new lines
    
    Returns:
        Formatted text with ▸ on new lines
    """
    import re
    import logging
    logger = logging.getLogger(__name__)
    
    # Count bullet points before fix
    bullet_count_before = text.count('▸')
    
    # Find first bullet location to show relevant sample
    first_bullet_idx = text.find('▸')
    if first_bullet_idx != -1:
        # Show 100 chars before and after first bullet
        start = max(0, first_bullet_idx - 100)
        end = min(len(text), first_bullet_idx + 200)
        sample_before = text[start:end]
        logger.info(f"[BULLET FIX] Sample around first bullet (BEFORE): ...{sample_before}...")
    else:
        logger.info(f"[BULLET FIX] No bullets found in text")
    
    logger.info(f"[BULLET FIX] Total ▸ found: {bullet_count_before}")
    
    # CRITICAL FIX: Replace ANY character (except newline) followed by ▸ 
    # Pattern: (non-newline char)(optional spaces)▸ → same char + newline + ▸
    # This handles: "chính: ▸", "text. ▸", "Item ▸", etc.
    text = re.sub(r'([^\n])\s*▸\s*', r'\1\n▸ ', text)
    
    # Show same area after fix
    if first_bullet_idx != -1:
        # Bullet might have moved due to added newlines, search again
        first_bullet_after = text.find('▸')
        if first_bullet_after != -1:
            start = max(0, first_bullet_after - 100)
            end = min(len(text), first_bullet_after + 200)
            sample_after = text[start:end]
            logger.info(f"[BULLET FIX] Sample around first bullet (AFTER): ...{sample_after}...")
    
    # Clean up: Remove bullet points at start of text (keep them)
    # Clean up: Ensure no more than 2 consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean up: Remove trailing spaces before newlines
    text = re.sub(r' +\n', '\n', text)
    
    return text


async def generate_answer_with_theoretical(
    question: str,
    theoretical_context: str = "",
    user_language: str = "vi",
    original_question: str = None,
    conversation_buffer: list = None,
    summary_context: str = ""
) -> str:
    """
    Generate answer for theoretical questions based on theoretical knowledge.
    
    Args:
        question: User question (may be translated)
        theoretical_context: Context from theoretical knowledge base
        user_language: User's language (vi/en)
        original_question: Original question if translated
        conversation_buffer: Recent conversation history
        summary_context: Summary of older conversation
    
    Returns:
        Generated answer string
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    # Get question (use original for Vietnamese)
    q = original_question if (user_language == "vi" and original_question) else question
    
    try:
        # Build conversation context if available
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
        
        if theoretical_context:
            context_parts.append(f"Theoretical Knowledge:\n{theoretical_context}")
        else:
            context_parts.append("No theoretical knowledge available.")
        
        if conversation_context:
            context_parts.append(f"\nConversation context:\n{conversation_context}")
        
        combined_context = "\n".join(context_parts)
        
        # Build full prompt
        user_message = user_template_theoretical.replace("{{QUESTION}}", q).replace(
            "{{THEORETICAL_CONTEXT}}",
            combined_context
        )
        
        full_prompt = f"{system_instructions_theoretical}\n\n{user_message}"

        # Generate answer
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        # Post-process: fix bullet point formatting
        answer = fix_bullet_formatting(answer)
        logger.info("✅ Applied bullet point formatting fix")
        
        return answer
        
    except Exception as e:
        logger.error(f"Failed to generate theoretical answer: {e}")
        return fallback_answer

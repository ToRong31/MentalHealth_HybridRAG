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
    Convert ▸ bullets to markdown list format for proper frontend rendering.
    
    ReactMarkdown collapses single newlines, so we need to convert:
    - "▸ Item" → "- Item" (markdown bullet)
    OR add double newlines for paragraph breaks
    
    Args:
        text: Input text that may have ▸ bullets
    
    Returns:
        Text with ▸ converted to markdown bullets
    """
    import re
    import logging
    logger = logging.getLogger(__name__)
    
    bullet_count = text.count('▸')
    logger.info(f"[BULLET FIX] Converting {bullet_count} bullets to markdown format")
    
    # SOLUTION: Convert ▸ to markdown bullets (-)
    # This ensures ReactMarkdown renders them as proper list items
    # Pattern: ▸ (at start of line or after newline) → - 
    text = re.sub(r'^▸\s*', '- ', text, flags=re.MULTILINE)
    
    # Also handle inline bullets (shouldn't happen but just in case)
    # If ▸ appears after text without newline, add newline first
    text = re.sub(r'([^\n])\s*▸\s*', r'\1\n- ', text)
    
    logger.info(f"[BULLET FIX] ✓ Converted to markdown bullets")
    
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

"""
Safety Check Node
Kiểm tra xem câu hỏi có phải high-risk không
UPGRADED: Context-aware với conversation history
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load safety check prompt
safety_check_prompt_data = load_prompts("safety_check_prompt.yaml")
safety_check_prompt = safety_check_prompt_data.get("safety_check_prompt", "")

if not safety_check_prompt:
    raise ValueError("Safety check prompt is empty! Check safety_check_prompt.yaml file.")


async def process_safety_check(
    question: str,
    history: str = "",
    summary_context: str = "",
    query_type: str = None,
    should_enhance: bool = False,
    conversation_buffer: list = None
) -> Dict[str, Any]:
    """
    Process safety check logic with CONTEXT AWARENESS.
    
    Args:
        question: User's latest question
        history: Formatted conversation history (already formatted from node)
        summary_context: Summary of conversation so far
        query_type: Type of query (legacy parameter, not used)
        should_enhance: Whether to enhance query (legacy parameter, not used)
        conversation_buffer: Legacy parameter for backward compatibility (not used)
    
    Returns:
        Dict with parsed_output containing:
        {
            "parsed_output": {
                "classification": "high_risk" | "safe",
                "reason": "...",
                "confidence": "high"|"medium"|"low",
                "indicators": [...]
            },
            "is_high_risk": bool  # For backward compatibility with routing
        }
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    # No query enhancement needed - history is already passed separately
    q = question
    logger.info(f"[SAFETY CHECK] Processing question with history context")
    logger.info(f"[SAFETY CHECK] History length: {len(history)} chars")
    logger.info(f"[SAFETY CHECK] Summary length: {len(summary_context)} chars")
    
    # Validate prompt
    if not safety_check_prompt:
        logger.error("Safety check prompt is empty!")
        raise ValueError("Safety check prompt is not loaded properly")
    
    # Create prompt with history + summary + question
    prompt = safety_check_prompt.replace("{{QUESTION}}", q)
    prompt = prompt.replace("{{HISTORY}}", history if history else "No previous conversation.")
    prompt = prompt.replace("{{SUMMARY_CONTEXT}}", summary_context if summary_context else "No summary available.")
    
    logger.info(f"[SAFETY CHECK] Prompt length: {len(prompt)} chars")
    logger.debug(f"[SAFETY CHECK] History preview: {history[:200]}...")
    
    # Call LLM
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        
        logger.debug(f"[SAFETY CHECK] LLM response: {response[:300]}...")
        
        # Parse JSON response with updated schema
        json_match = re.search(
            r'\{[^{}]*"classification"[^{}]*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            # Map to output format
            classification = result.get("classification", "safe")
            is_high_risk = (classification == "high_risk")
            
            logger.info(f"[SAFETY CHECK] Parsed classification: {classification}, is_high_risk: {is_high_risk}")
            
            return {
                "parsed_output": result,
                "is_high_risk": is_high_risk  # For backward compatibility with routing logic
            }
        else:
            logger.warning(f"[SAFETY CHECK] Could not parse JSON from LLM response: {response[:200]}")
            return {
                "parsed_output": {
                    "classification": "safe",
                    "reason": "Failed to parse LLM response",
                    "confidence": "low"
                },
                "is_high_risk": False
            }
            
    except Exception as e:
        logger.error(f"[SAFETY CHECK] Error in process_safety_check: {e}", exc_info=True)
        return {
            "parsed_output": {
                "classification": "safe",
                "reason": f"Error during processing: {str(e)}",
                "confidence": "low"
            },
            "is_high_risk": False
        }

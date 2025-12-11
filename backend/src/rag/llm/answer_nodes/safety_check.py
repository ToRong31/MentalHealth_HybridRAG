"""
Safety Check Node
Kiểm tra xem câu hỏi có liên quan đến mental health và có phải high-risk không
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


async def safety_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kiểm tra xem câu hỏi có liên quan đến mental health và có phải high-risk không (async version).
    
    Args:
        state: State dict với 'question' key
    
    Returns:
        Updated state với 'is_mental_health_related' và 'is_high_risk'
    """
    q = state["question"]
    
    # Validate prompt
    if not safety_check_prompt:
        logger.error("Safety check prompt is empty!")
        raise ValueError("Safety check prompt is not loaded properly")
    
    # Tạo prompt với câu hỏi của user
    prompt = safety_check_prompt.replace("{{QUESTION}}", q)
    
    logger.info(f"Safety check prompt length: {len(prompt)}")
    
    # Gọi LLM để phân tích (run in executor to avoid blocking)
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(prompt))
        
        # Parse JSON response
        # Tìm JSON trong response (phòng trường hợp LLM trả về text thêm)
        json_match = re.search(
            r'\{[^{}]*"is_mental_health_related"[^{}]*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            state["is_mental_health_related"] = result.get(
                "is_mental_health_related",
                True
            )
            state["is_high_risk"] = result.get("is_high_risk", False)
        else:
            # Fallback: nếu không parse được JSON, mặc định là mental health related
            print(f"Warning: Could not parse JSON from LLM response: {response}")
            state["is_mental_health_related"] = True
            state["is_high_risk"] = False
            
    except Exception as e:
        print(f"Error in safety_check_node: {e}")
        # Fallback an toàn: cho phép tiếp tục
        state["is_mental_health_related"] = True
        state["is_high_risk"] = False
    
    return state

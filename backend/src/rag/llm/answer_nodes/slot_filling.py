"""
Slot Filling Node
Extract structured information (slots) from user question and identify missing information
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt
from src.rag.slots.utils import get_default_slots

logger = logging.getLogger(__name__)


async def slot_filling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract structured information (slots) from user question and identify missing information.
    Only runs after safety_check confirms safe & relevant.
    
    Args:
        state: KGState with 'question', 'user_language'
    
    Returns:
        Updated state with 'slots', 'missing_slots', 'relevant_missing_slots', 'follow_up_questions'
    """
    question = state["question"]

    try:
        # Load slot filling prompt
        prompt_data = load_prompts("slot_filling_prompt.yaml")
        prompt_template = prompt_data.get("slot_filling_prompt", "")
        
        if not prompt_template:
            logger.warning("Slot filling prompt not found, using defaults")
            state["slots"] = get_default_slots()
            state["missing_slots"] = []
            state["relevant_missing_slots"] = []
            state["follow_up_questions"] = []
            return state
        
        # Format prompt with question
        prompt = format_prompt(prompt_template, QUESTION=question)
        
        # Call LLM (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        # Parse JSON response
        json_match = re.search(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            # Update state
            state["slots"] = result.get("slots", get_default_slots())
            state["missing_slots"] = result.get("missing_slots", [])
            state["relevant_missing_slots"] = result.get("relevant_missing_slots", [])
            state["follow_up_questions"] = result.get("follow_up_questions", [])
            
            logger.info(
                f"Extracted slots: {len([v for v in state['slots'].values() if v is not None and v != []])} filled, "
                f"{len(state.get('relevant_missing_slots', []))} relevant missing, "
                f"{len(state.get('follow_up_questions', []))} follow-ups"
            )
        else:
            logger.warning(f"Could not parse JSON from slot filling response: {response[:200]}")
            # Fallback to defaults
            state["slots"] = get_default_slots()
            state["missing_slots"] = []
            state["relevant_missing_slots"] = []
            state["follow_up_questions"] = []
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in slot_filling_node: {e}")
        state["slots"] = get_default_slots()
        state["missing_slots"] = []
        state["relevant_missing_slots"] = []
        state["follow_up_questions"] = []
    except Exception as e:
        logger.error(f"Error in slot_filling_node: {e}", exc_info=True)
        # Fallback to defaults on error
        state["slots"] = get_default_slots()
        state["missing_slots"] = []
        state["relevant_missing_slots"] = []
        state["follow_up_questions"] = []
    
    return state

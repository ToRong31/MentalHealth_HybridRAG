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
from src.rag.utils.slots import get_default_slots

logger = logging.getLogger(__name__)


async def process_slot_filling(question: str, existing_slots: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Extract structured information (slots) from user question using LLM.
    
    Args:
        question: User question
        existing_slots: Slots from previous turns (to avoid asking again)
    
    Returns:
        Dict with slots, missing_slots, relevant_missing_slots, follow_up_questions
    """
    try:
        # Load slot filling prompt
        logger.info("[SLOT FILLING LLM] Loading prompt from slot_filling_prompt.yaml...")
        prompt_data = await load_prompts("slot_filling_prompt.yaml")
        prompt_template = prompt_data.get("slot_filling_prompt", "")
        
        if not prompt_template:
            logger.error("[SLOT FILLING LLM] ❌ Prompt template is EMPTY! Cannot extract slots.")
            return {
                "slots": get_default_slots(),
                "missing_slots": [],
                "relevant_missing_slots": [],
                "follow_up_questions": []
            }
        
        logger.info(f"[SLOT FILLING LLM] ✅ Prompt loaded successfully (length: {len(prompt_template)})")
        
        # Build existing slots context to avoid re-asking
        existing_slots_str = ""
        if existing_slots:
            filled_slots = {k: v for k, v in existing_slots.items() 
                          if v not in [None, [], "none", "unknown"]}
            if filled_slots:
                existing_slots_str = "\n\n========== ALREADY FILLED SLOTS (DO NOT ASK AGAIN) ==========\n"
                for key, value in filled_slots.items():
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value) if value else "[]"
                    else:
                        value_str = str(value)
                    existing_slots_str += f"- {key}: {value_str}\n"
                existing_slots_str += "\n⚠️ CRITICAL: Do NOT include these slots in relevant_missing_slots or ask follow-up questions about them.\n"
        
        # Format prompt with question and existing slots
        prompt = format_prompt(prompt_template, QUESTION=question, EXISTING_SLOTS=existing_slots_str)
        
        logger.info(f"[SLOT FILLING LLM] Formatted prompt length: {len(prompt)}")
        logger.debug(f"[SLOT FILLING LLM] Question: {question[:100]}...")
        
        # Call LLM
        logger.info("[SLOT FILLING LLM] Calling LLM to extract slots...")
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: llm.invoke(prompt, max_retries=3)
        )
        
        logger.info(f"[SLOT FILLING LLM] ✅ LLM response received (length: {len(response)})")
        logger.debug(f"[SLOT FILLING LLM] Response preview: {response[:200]}...")
        
        # Parse JSON response
        json_match = re.search(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            slots = result.get("slots", get_default_slots())
            missing_slots = result.get("missing_slots", [])
            relevant_missing_slots = result.get("relevant_missing_slots", [])
            follow_up_questions = result.get("follow_up_questions", [])
            
            # ========== BEGIN: DETAILED SLOT FILLING LOGS (Remove this block when done debugging) ==========
            filled_slots = {k: v for k, v in slots.items() 
                          if v is not None and v != [] and v != "none"}
            
            logger.info("="*80)
            logger.info("SLOT FILLING RESULTS")
            logger.info("="*80)
            logger.info(f"✅ Filled slots ({len(filled_slots)}):")
            for key, value in filled_slots.items():
                if isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value) if value else "[]"
                else:
                    value_str = str(value)
                logger.info(f"   • {key}: {value_str}")
            
            logger.info(f"\n❌ Missing slots ({len(missing_slots)}):")
            logger.info(f"   {', '.join(missing_slots) if missing_slots else 'None'}")
            
            logger.info(f"\n🎯 Relevant missing slots ({len(relevant_missing_slots)}):")
            logger.info(f"   {', '.join(relevant_missing_slots) if relevant_missing_slots else 'None'}")
            
            logger.info(f"\n💬 Follow-up questions ({len(follow_up_questions)}):")
            for i, q in enumerate(follow_up_questions, 1):
                logger.info(f"   {i}. {q}")
            logger.info("="*80)
            # ========== END: DETAILED SLOT FILLING LOGS ==========

            return {
                "slots": slots,
                "missing_slots": missing_slots,
                "relevant_missing_slots": relevant_missing_slots,
                "follow_up_questions": follow_up_questions
            }
        else:
            logger.warning(f"Could not parse JSON from slot filling response: {response[:200]}")
            return {
                "slots": get_default_slots(),
                "missing_slots": [],
                "relevant_missing_slots": [],
                "follow_up_questions": []
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in process_slot_filling: {e}")
        return {
            "slots": get_default_slots(),
            "missing_slots": [],
            "relevant_missing_slots": [],
            "follow_up_questions": []
        }
    except Exception as e:
        logger.error(f"Error in process_slot_filling: {e}", exc_info=True)
        return {
            "slots": get_default_slots(),
            "missing_slots": [],
            "relevant_missing_slots": [],
            "follow_up_questions": []
        }
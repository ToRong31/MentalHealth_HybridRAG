"""
Slot Filling Node
Node wrapper for slot filling logic
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes.slot_filling import process_slot_filling
from src.rag.utils.slots import has_sufficient_slots, merge_slots, get_default_slots
from src.rag.utils.slot_utils import filter_follow_up_for_required_only

logger = logging.getLogger(__name__)


async def slot_filling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Extract structured information (slots) from user question + conversation context.
    Slots are MERGED across turns (append instead of replace) for persistent state.
    Filters follow-up questions to prioritize REQUIRED slots when insufficient.
    
    Args:
        state: State dict with question, conversation_buffer, summary_context, slots (from previous turns)
    
    Returns:
        Updated state with merged slots, has_sufficient_slots, 
        filtered_follow_up_questions (only REQUIRED if insufficient)
    """
    question = state["question"]
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    # Get existing slots from state (from previous turns via checkpointer)
    existing_slots = state.get("slots")
    
    # Initialize with defaults if first turn
    if not existing_slots:
        existing_slots = get_default_slots()
        logger.info("[SLOT FILLING] First turn - initialized empty slots")
    else:
        logger.info(f"[SLOT FILLING] Existing slots from previous turns: {len([k for k, v in existing_slots.items() if v and v != [] and v != 'none'])} filled")
    
    # Build enhanced context for slot extraction
    # Include conversation history so LLM can extract slots from full context
    enhanced_question = question
    if conversation_buffer or summary_context:
        context_parts = []
        
        if summary_context:
            context_parts.append(f"Previous conversation summary: {summary_context}")
        
        if conversation_buffer:
            context_parts.append("Recent conversation:")
            for i, pair in enumerate(conversation_buffer[-3:], 1):  # Last 3 pairs
                context_parts.append(f"Q{i}: {pair.get('user', '')}")
                context_parts.append(f"A{i}: {pair.get('bot', '')}")
        
        context_parts.append(f"\nCurrent question: {question}")
        enhanced_question = "\n".join(context_parts)
        
        logger.info(f"[SLOT FILLING] Extracting from enhanced context with {len(conversation_buffer)} buffer pairs and summary")
    
    # Call logic function with enhanced context to extract NEW slots from current turn
    # Pass existing_slots so LLM knows what NOT to ask again
    result = await process_slot_filling(enhanced_question, existing_slots=existing_slots)
    new_slots = result.get("slots", {})
    
    # MERGE new slots with existing slots (append instead of replace)
    merged_slots = merge_slots(existing_slots, new_slots)
    
    # Log the merge
    new_filled_count = len([k for k, v in new_slots.items() if v and v != [] and v != 'none'])
    merged_filled_count = len([k for k, v in merged_slots.items() if v and v != [] and v != 'none'])
    logger.info(f"[SLOT FILLING] Merge complete: {new_filled_count} new slots + existing → {merged_filled_count} total filled slots")
    
    # Update result with merged slots
    result["slots"] = merged_slots
    
    # Check if REQUIRED slots are sufficient for retrieval
    is_sufficient, required_missing, _ = has_sufficient_slots(merged_slots)
    
    logger.info(f"[DEBUG] is_sufficient = {is_sufficient}, required_missing = {required_missing}")
    logger.info(f"[DEBUG] Filled REQUIRED slots: {[s for s in ['emotion', 'primary_mood', 'intensity', 'trigger', 'duration', 'impact', 'need', 'stress_level'] if merged_slots.get(s) not in [None, [], 'none']]}")
    
    # Get follow-up questions and relevant missing slots
    follow_up_questions = result.get("follow_up_questions", [])
    relevant_missing_slots = result.get("relevant_missing_slots", [])
    
    # Separate relevant_missing_slots into REQUIRED vs OPTIONAL
    from src.rag.utils.slots import REQUIRED_SLOTS
    required_set = set(REQUIRED_SLOTS)
    
    required_relevant = [s for s in relevant_missing_slots if s in required_set]
    optional_relevant = [s for s in relevant_missing_slots if s not in required_set]
    
    # If REQUIRED slots insufficient → Only ask about REQUIRED slots
    if not is_sufficient:
        # Filter to keep only questions about REQUIRED slots
        filtered_questions = filter_follow_up_for_required_only(
            follow_up_questions,
            relevant_missing_slots
        )
        result["follow_up_questions"] = filtered_questions
        result["optional_follow_up_questions"] = []  # Don't ask optional yet
        
        logger.info(f"❌ Insufficient REQUIRED slots. Asking {len(filtered_questions)} REQUIRED questions only")
        logger.info(f"   Missing REQUIRED: {required_missing}")
        logger.info(f"   Optional questions deferred until REQUIRED slots filled")
    else:
        # REQUIRED sufficient → Save optional questions for answer node
        # Filter to get only OPTIONAL questions for later
        optional_questions = []
        for i, slot_name in enumerate(relevant_missing_slots):
            if slot_name not in required_set and i < len(follow_up_questions):
                optional_questions.append(follow_up_questions[i])
        
        result["follow_up_questions"] = []  # Don't block with questions
        result["optional_follow_up_questions"] = optional_questions  # Save for answer
        
        logger.info(f"✅ Sufficient REQUIRED slots filled for retrieval")
        logger.info(f"   Optional relevant slots: {optional_relevant}")
        if optional_questions:
            logger.info(f"   Will include {len(optional_questions)} optional questions in answer")
            for i, q in enumerate(optional_questions):
                logger.info(f"     {i+1}. {q}")
        else:
            logger.info(f"   No optional questions to ask (all relevant slots are REQUIRED)")
    
    # Add sufficiency check results to result dict (LangGraph will merge this into state)
    result["has_sufficient_slots"] = is_sufficient
    result["required_missing_slots"] = required_missing
    
    logger.info(f"[DEBUG] Returning result with has_sufficient_slots = {result.get('has_sufficient_slots')}")
    logger.info(f"[DEBUG] Result keys: {list(result.keys())}")
    
    # Update state as well (belt and suspenders approach)
    state.update(result)
    
    return state

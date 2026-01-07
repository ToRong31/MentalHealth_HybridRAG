"""
Slot Filling Node
Node wrapper for slot filling logic
REDESIGNED: Uses DSM-5 stage-based intake flow
"""
import logging
from typing import Dict, Any

from src.rag.llm.answer_nodes.slot_filling import process_slot_filling
from src.rag.utils.slots import (
    has_sufficient_slots, 
    merge_slots, 
    get_default_slots,
    get_current_stage,
    next_missing_slot,
    is_intake_complete,
    is_empty_slot
)
from src.rag.utils.slot_utils import filter_follow_up_for_required_only

logger = logging.getLogger(__name__)


async def slot_filling_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Extract structured information (slots) from user question + conversation context.
    REDESIGNED: Follows DSM-5 stage-based intake flow.
    
    Workflow:
    1. Determine current stage in intake flow
    2. Extract new slots from user input
    3. Merge with existing slots (preserving "no" responses)
    4. Update stage progression
    5. Filter follow-up questions by stage priority
    
    Args:
        state: State dict with question, conversation_buffer, summary_context, slots (from previous turns)
    
    Returns:
        Updated state with:
        - merged slots
        - current_stage
        - intake_complete
        - has_sufficient_slots
        - filtered follow_up_questions
        - optional_follow_up_questions
    """
    question = state["question"]
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    # Get existing slots from state (from previous turns via checkpointer)
    existing_slots = state.get("slots")
    
    # Initialize with defaults if first turn
    if not existing_slots:
        existing_slots = get_default_slots()
        logger.info("[SLOT FILLING] First turn - initialized default slots")
    else:
        filled_count = len([k for k, v in existing_slots.items() if not is_empty_slot(v)])
        logger.info(f"[SLOT FILLING] Existing slots from previous turns: {filled_count} filled")
    
    # Determine current stage
    current_stage = get_current_stage(existing_slots)
    next_stage, next_slot = next_missing_slot(existing_slots)
    
    logger.info(f"[SLOT FILLING] Current stage: {current_stage}")
    if next_slot:
        logger.info(f"[SLOT FILLING] Next required: {next_stage}.{next_slot}")
    
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
    
    # MERGE new slots with existing slots (append instead of replace, preserve "no" responses)
    merged_slots = merge_slots(existing_slots, new_slots)
    
    # Log the merge
    new_filled_count = len([k for k, v in new_slots.items() if not is_empty_slot(v)])
    merged_filled_count = len([k for k, v in merged_slots.items() if not is_empty_slot(v)])
    logger.info(f"[SLOT FILLING] Merge complete: {new_filled_count} new slots + existing → {merged_filled_count} total filled slots")
    
    # Update result with merged slots
    result["slots"] = merged_slots
    
    # Update stage info
    current_stage = get_current_stage(merged_slots)
    result["current_stage"] = current_stage
    
    # Check intake completion
    intake_done = is_intake_complete(merged_slots)
    result["intake_complete"] = intake_done
    
    # Check if REQUIRED slots are sufficient for retrieval (backward compatibility)
    is_sufficient, required_missing, differential_missing = has_sufficient_slots(merged_slots)
    result["has_sufficient_slots"] = is_sufficient
    result["required_missing_slots"] = required_missing
    
    # Log progress
    logger.info(f"[SLOT FILLING] Stage: {current_stage} | Intake complete: {intake_done}")
    logger.info(f"[SLOT SUFFICIENCY] is_sufficient = {is_sufficient}")
    logger.info(f"[SLOT SUFFICIENCY] required_missing = {required_missing}")
    
    if not intake_done:
        next_stage, next_slot = next_missing_slot(merged_slots)
        logger.info(f"[SLOT FILLING] Next required: {next_stage}.{next_slot}")
    
    # Get follow-up questions and relevant missing slots
    follow_up_questions = result.get("follow_up_questions", [])
    relevant_missing_slots = result.get("relevant_missing_slots", [])
    
    # If REQUIRED slots insufficient → Only ask about REQUIRED slots (focused on current stage)
    if not is_sufficient:
        # Filter to keep only questions about REQUIRED slots
        filtered_questions = filter_follow_up_for_required_only(
            follow_up_questions,
            relevant_missing_slots
        )
        result["follow_up_questions"] = filtered_questions
        result["optional_follow_up_questions"] = []  # Don't ask optional yet
        
        logger.info(f"❌ Incomplete required slots. Asking {len(filtered_questions)} REQUIRED questions")
        logger.info(f"   Focusing on stage: {next_stage}")
        logger.info(f"   Missing REQUIRED: {required_missing[:5]}...")  # First 5
        logger.info(f"   Optional questions deferred until REQUIRED slots filled")
    else:
        # REQUIRED sufficient → Save optional questions for answer node
        # All relevant questions become optional at this point
        result["follow_up_questions"] = []  # Don't block with questions
        result["optional_follow_up_questions"] = follow_up_questions  # Save for answer
        
        logger.info(f"✅ Sufficient REQUIRED slots filled for retrieval")
        logger.info(f"   Optional relevant slots: {relevant_missing_slots[:5]}...")  # First 5
        if follow_up_questions:
            logger.info(f"   Will include {len(follow_up_questions)} optional questions in answer")
            for i, q in enumerate(follow_up_questions[:3]):  # Log first 3
                logger.info(f"     {i+1}. {q}")
        else:
            logger.info(f"   No optional questions to ask")
    
    logger.info(f"[DEBUG] Returning result with has_sufficient_slots = {result.get('has_sufficient_slots')}")
    logger.info(f"[DEBUG] Result keys: {list(result.keys())}")
    
    # Update state as well (belt and suspenders approach)
    state.update(result)
    
    return state

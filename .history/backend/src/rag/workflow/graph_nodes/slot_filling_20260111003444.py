"""
Slot Filling Node
Node wrapper for slot filling logic
REDESIGNED: Uses DSM-5 stage-based intake flow
"""
import logging
import re
from typing import Dict, Any, List

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


def _post_process_slot_extraction(slots: Dict[str, Any], conversation_buffer: List[Dict], current_question: str) -> Dict[str, Any]:
    """
    Post-processing to catch information LLM might have missed.
    Uses regex and keyword matching to extract obvious patterns from conversation history.
    
    Args:
        slots: Currently extracted slots
        conversation_buffer: Full conversation history
        current_question: Current user question
        
    Returns:
        Updated slots with additional extracted information
    """
    # Build full conversation text
    conversation_text = ""
    for pair in conversation_buffer:
        user_msg = pair.get('user', '')
        bot_msg = pair.get('bot', '')
        conversation_text += f"User: {user_msg}\n"
        conversation_text += f"Bot: {bot_msg}\n"
    conversation_text += f"User: {current_question}\n"
    
    conversation_lower = conversation_text.lower()
    
    # PATTERN 1: Medical history - "no medical conditions", "no underlying disease"
    if is_empty_slot(slots.get("medical_history_any")) or slots.get("medical_history_any") == "unknown":
        no_medical_patterns = [
            r"no\s+(underlying\s+)?(medical\s+)?(conditions?|diseases?|illness)",
            r"(don't|do not|doesn't)\s+have\s+any\s+(medical\s+)?(conditions?|diseases?)",
            r"không\s+có\s+bệnh\s+nền",
            r"không\s+mắc\s+bệnh"
        ]
        for pattern in no_medical_patterns:
            if re.search(pattern, conversation_lower):
                slots["medical_history_any"] = "no"
                if is_empty_slot(slots.get("medical_history")):
                    slots["medical_history"] = ["no medical conditions"]
                logger.info(f"[POST-PROCESS] Detected medical_history_any='no' from pattern: {pattern}")
                break
    
    # PATTERN 2: Substance use - "no stimulants", "don't use substances"
    if is_empty_slot(slots.get("substance_use_any")) or slots.get("substance_use_any") == "unknown":
        no_substance_patterns = [
            r"(don't|do not|doesn't)\s+use\s+(any\s+)?(substances?|drugs?|stimulants?)",
            r"no\s+(substance|drug|stimulant)\s+use",
            r"không\s+dùng\s+(chất\s+)?(kích\s+thích|ma\s+túy)",
            r"không\s+sử\s+dụng\s+chất"
        ]
        for pattern in no_substance_patterns:
            if re.search(pattern, conversation_lower):
                slots["substance_use_any"] = "no"
                if is_empty_slot(slots.get("substance_use")):
                    slots["substance_use"] = ["no substance use"]
                logger.info(f"[POST-PROCESS] Detected substance_use_any='no' from pattern: {pattern}")
                break
    
    # PATTERN 3: Caffeine/nicotine - "no stimulants", "don't drink coffee"
    if is_empty_slot(slots.get("caffeine_nicotine_use")):
        no_caffeine_patterns = [
            r"(don't|do not)\s+(drink|use)\s+(coffee|caffeine)",
            r"no\s+(caffeine|coffee|nicotine)",
            r"không\s+(uống\s+)?(cà\s+phê|cafe)",
            r"không\s+dùng\s+chất\s+kích\s+thích"
        ]
        for pattern in no_caffeine_patterns:
            if re.search(pattern, conversation_lower):
                if is_empty_slot(slots.get("caffeine_nicotine_use")):
                    slots["caffeine_nicotine_use"] = ["no caffeine/nicotine use"]
                logger.info(f"[POST-PROCESS] Detected caffeine_nicotine_use='no' from pattern: {pattern}")
                break
    
    # PATTERN 4: Frequency - "every day", "daily", "all day"
    if is_empty_slot(slots.get("frequency")):
        frequency_patterns = [
            (r"(every\s+day|daily|each\s+day)", "daily"),
            (r"(all\s+day|entire\s+day|whole\s+day)", "all day"),
            (r"hàng\s+ngày", "daily"),
            (r"(gần\s+như|suốt)\s+(cả\s+ngày|ngày)", "almost all day"),
            (r"liên\s+tục", "continuous")
        ]
        for pattern, value in frequency_patterns:
            if re.search(pattern, conversation_lower):
                if is_empty_slot(slots.get("frequency")):
                    slots["frequency"] = [value]
                logger.info(f"[POST-PROCESS] Detected frequency='{value}' from pattern: {pattern}")
                break
    
    # PATTERN 5: Self-care functioning - "struggle to shower", "lazy to eat", "weight loss"
    if is_empty_slot(slots.get("self_care_functioning")):
        self_care_issues = []
        
        hygiene_patterns = [
            (r"(struggle|hard|difficult)\s+to\s+(shower|bathe|wash)", "difficulty with hygiene - struggle to shower"),
            (r"(đấu\s+tranh|khó\s+khăn)\s+(mới\s+)?(tắm|vệ\s+sinh)", "difficulty with hygiene - struggle to shower"),
            (r"(lazy|hard)\s+to\s+(chew|eat)", "difficulty with eating - lazy to chew"),
            (r"lười\s+(nhai|ăn)", "difficulty with eating - lazy to chew"),
            (r"(weight\s+loss|losing\s+weight|sụt\s+cân)", "weight loss")
        ]
        
        for pattern, description in hygiene_patterns:
            if re.search(pattern, conversation_lower):
                self_care_issues.append(description)
                logger.info(f"[POST-PROCESS] Detected self_care issue: {description}")
        
        if self_care_issues:
            slots["self_care_functioning"] = self_care_issues
    
    return slots


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
    
    # NEW: Get empathy_preamble
    empathy_preamble_vi = result.get("empathy_preamble_vi", "")
    
    # MERGE new slots with existing slots (append instead of replace, preserve "no" responses)
    merged_slots = merge_slots(existing_slots, new_slots)
    
    # POST-PROCESSING: Additional semantic extraction from conversation buffer
    # This catches information LLM might have missed
    merged_slots = _post_process_slot_extraction(merged_slots, conversation_buffer, question)
    
    logger.info(f"[SLOT FILLING] Post-processing complete")
    
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
    
    # NEW: Add empathy to result
    result["empathy_preamble_vi"] = empathy_preamble_vi
    
    logger.info(f"[DEBUG] Returning result with has_sufficient_slots = {result.get('has_sufficient_slots')}")
    logger.info(f"[DEBUG] Empathy preamble: {empathy_preamble_vi[:80] if empathy_preamble_vi else '(none)'}")
    logger.info(f"[DEBUG] Result keys: {list(result.keys())}")
    
    # Update state as well (belt and suspenders approach)
    state.update(result)
    
    return state

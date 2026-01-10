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
from src.rag.prompts.loader import load_prompts_async, format_prompt
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
        prompt_data = await load_prompts_async("slot_filling_prompt.yaml")
        prompt_template = prompt_data.get("slot_filling_prompt", "")
        
        if not prompt_template:
            logger.warning("Slot filling prompt not found, using defaults")
            return {
                "slots": get_default_slots(),
                "missing_slots": [],
                "relevant_missing_slots": [],
                "follow_up_questions": []
            }
        
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
        prompt = format_prompt(prompt_template, QUESTION=question) + existing_slots_str
        
        # Call LLM
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
            
            slots = result.get("slots", get_default_slots())
            missing_slots = result.get("missing_slots", [])
            relevant_missing_slots = result.get("relevant_missing_slots", [])
            follow_up_questions = result.get("follow_up_questions", [])
            
            # ========== NEW: Parse empathy_preamble ==========
            empathy_preamble_vi = result.get("empathy_preamble_vi", "")
            
            # Validate empathy (không được là câu hỏi)
            if empathy_preamble_vi and "?" in empathy_preamble_vi:
                logger.warning(f"⚠️ Empathy preamble contains question mark: '{empathy_preamble_vi}'")
                logger.warning("   Empathy should not be a question - using fallback")
                empathy_preamble_vi = ""  # Clear invalid empathy
            
            logger.info(f"\n💙 Empathy preamble: {empathy_preamble_vi if empathy_preamble_vi else '(not generated)'}")
            # ========== END NEW ==========
            
            # ========== VALIDATION: Enforce 1-3 questions limit ==========
            original_question_count = len(follow_up_questions)
            
            # Check if there are missing REQUIRED slots
            REQUIRED_SLOTS = [
                "presenting_problem", "emotion", "primary_mood",
                "onset", "duration", "frequency", "symptom_fluctuation",
                "intensity", "distress_level", "stress_level",
                "daily_functioning", "work_school_impact", "social_functioning", "self_care_functioning",
                "trigger", "current_stressors", "recent_life_events",
                "substance_use_any", "medical_history_any", "medication_changes", "caffeine_nicotine_use",
                "support_system", "coping_mechanisms",
                "mania_like_symptoms", "psychotic_like_symptoms"
            ]
            
            missing_required = []
            for slot in REQUIRED_SLOTS:
                value = slots.get(slot)
                # Check if slot is empty or unknown
                if value is None or value == [] or value == "unknown" or value == "":
                    missing_required.append(slot)
            
            # RULE 1: If missing required slots but NO questions → Generate fallback questions
            if missing_required and not follow_up_questions:
                logger.warning(f"⚠️ VALIDATION FAILED: {len(missing_required)} required slots missing but LLM generated NO questions!")
                logger.warning(f"   Missing required: {missing_required[:5]}...")
                
                # Auto-generate specific questions for top 3 priority missing slots
                SLOT_TO_QUESTION = {
                    "emotion": "Bạn đang cảm thấy cảm xúc gì cụ thể? (lo lắng, buồn, cáu gắt...)",
                    "presenting_problem": "Vấn đề chính khiến bạn tìm đến hỗ trợ là gì?",
                    "onset": "Tình trạng này bắt đầu từ khi nào? (số ngày/tuần/tháng)",
                    "duration": "Đã kéo dài bao lâu rồi? (số ngày/tuần/tháng)",
                    "intensity": "Mức độ nghiêm trọng của triệu chứng? (nhẹ, trung bình, nặng)",
                    "frequency": "Tình trạng này diễn ra với tần suất như thế nào? (mỗi ngày, vài lần/tuần...)",
                    "distress_level": "Mức độ khó chịu/đau khổ mà bạn đang trải qua? (thang điểm 0-10)",
                    "trigger": "Có sự kiện hay tình huống nào khiến bạn cảm thấy như vậy không?",
                    "work_school_impact": "Tình trạng này có ảnh hưởng đến công việc/học tập của bạn không?",
                    "daily_functioning": "Khả năng thực hiện các hoạt động hàng ngày của bạn có bị ảnh hưởng không?",
                }
                
                # Generate questions for top 3 missing slots (prioritize Stage 1-2)
                for slot in missing_required[:3]:
                    if slot in SLOT_TO_QUESTION:
                        follow_up_questions.append(SLOT_TO_QUESTION[slot])
                
                logger.info(f"   → Auto-generated {len(follow_up_questions)} fallback questions")
            
            # RULE 2: If more than 3 questions → Trim to top 3
            if len(follow_up_questions) > 3:
                logger.warning(f"⚠️ VALIDATION: LLM generated {len(follow_up_questions)} questions (exceeds limit of 3)")
                follow_up_questions = follow_up_questions[:3]
                logger.info(f"   → Trimmed to {len(follow_up_questions)} questions")
            
            # RULE 3: Check for generic questions and warn
            GENERIC_PATTERNS = [
                "chia sẻ thêm",
                "kể thêm",
                "nói thêm",
                "mô tả thêm",
                "chi tiết hơn",
                "giải thích thêm"
            ]
            
            for i, q in enumerate(follow_up_questions):
                if any(pattern in q.lower() for pattern in GENERIC_PATTERNS):
                    logger.warning(f"⚠️ VALIDATION: Question {i+1} appears generic: '{q}'")
            
            if original_question_count != len(follow_up_questions):
                logger.info(f"[VALIDATION] Questions adjusted: {original_question_count} → {len(follow_up_questions)}")
            # ========== END VALIDATION ==========
            
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
                "follow_up_questions": follow_up_questions,
                "empathy_preamble_vi": empathy_preamble_vi
            }
        else:
            logger.warning(f"Could not parse JSON from slot filling response: {response[:200]}")
            return {
                "slots": get_default_slots(),
                "missing_slots": [],
                "relevant_missing_slots": [],
                "follow_up_questions": [],
                "empathy_preamble_vi": ""
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in process_slot_filling: {e}")
        return {
            "slots": get_default_slots(),
            "missing_slots": [],
            "relevant_missing_slots": [],
            "follow_up_questions": [],
            "empathy_preamble_vi": ""
        }
    except Exception as e:
        logger.error(f"Error in process_slot_filling: {e}", exc_info=True)
        return {
            "slots": get_default_slots(),
            "missing_slots": [],
            "relevant_missing_slots": [],
            "follow_up_questions": [],
            "empathy_preamble_vi": ""
        }

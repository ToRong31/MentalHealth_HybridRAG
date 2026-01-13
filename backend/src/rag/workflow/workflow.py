from langgraph.graph import StateGraph, END
from typing import Literal
import logging

from .state import KGState
from .checkpointer import get_checkpointer 
from .graph_nodes import (
    encode_node,
    graph_retrieval_node,
    translate_question_node,
    translate_answer_node,
    safety_check_node,
    crisis_response_node,
    crisis_immediate_response_node,
    crisis_follow_up_classifier_node,
    crisis_escalation_node,
    crisis_contextual_support_node,
    crisis_gentle_persistence_node,
    crisis_to_normal_transition_node,
    not_mental_health_node,
    answer_with_graph_node,
    slot_filling_node,
    query_type_classifier_node,
    router_node,
    query_rewriter_node,
    conversation_memory_node,
    request_more_info_node,
    answer_with_theoretical_node,
    theoretical_retrieval_node,
    assessment_node,
    normal_coping_retrieval_node,
    adjustment_retrieval_node,
)

# Import new diagnostic and treatment nodes
from .graph_nodes.diagnostic_retrieval import diagnostic_retrieval_node
from .graph_nodes.disease_conclusion import disease_conclusion_node
from .graph_nodes.treatment_retrieval import treatment_retrieval_node
from .graph_nodes.answer_with_treatment import answer_with_treatment_node

logger = logging.getLogger(__name__)


def route_after_safety_check(state: KGState) -> Literal["crisis_immediate_response", "crisis_escalation", "crisis_to_normal_transition", "slot_filling"]:
    """
    Routing logic sau khi check safety:
    - Nếu high-risk -> crisis_immediate_response (NEW: multi-stage crisis flow)
    - Nếu safe nhưng có recent crisis -> crisis_to_normal_transition (follow-up)
    - Nếu safe -> slot_filling (personal questions đã được filter trước đó)
    
    UPGRADED: Re-enabled with context-aware safety check + adaptive crisis response
    """
    is_high_risk = state.get("is_high_risk", False)
    requires_monitoring = state.get("requires_safety_monitoring", False)
    recent_crisis = state.get("recent_crisis_detected", False)
    
    if is_high_risk:
        # Check if already in crisis flow (re-escalation)
        if state.get("crisis_stage"):
            logger.critical("[ROUTE] 🚨 RE-ESCALATION → crisis_escalation")
            return "crisis_escalation"
        else:
            # First time detect
            logger.critical("[ROUTE] 🚨 HIGH RISK → crisis_immediate_response")
            return "crisis_immediate_response"
    
    elif recent_crisis:
        # User had crisis recently but current message is safe
        # Need gentle follow-up before returning to normal flow
        logger.warning(f"[ROUTE] 🔄 RECENT CRISIS → crisis_to_normal_transition (gentle follow-up)")
        return "crisis_to_normal_transition"
    
    elif requires_monitoring:
        # User từng ở crisis, giờ stable nhưng cần watch closely
        logger.warning(f"[ROUTE] 👀 POST-CRISIS MONITORING → slot_filling (heightened sensitivity)")
        state["crisis_sensitivity_increased"] = True
    
    # Safe personal question - go through full diagnostic flow
    logger.info("[ROUTE] ✅ SAFE → slot_filling")
    return "slot_filling"


def route_after_classify_query(state: KGState) -> Literal["router", "not_mental_health"]:
    """
    Routing logic sau khi classify query:
    - Nếu off_topic -> not_mental_health (reject ngay)
    - Nếu follow_up hoặc topic_change -> router (phân loại tiếp)
    """
    query_type = state.get("query_type")
    
    if query_type == "off_topic":
        return "not_mental_health"
    
    # follow_up or topic_change -> classify personal/theoretical
    return "router"

def route_after_router(state: KGState) -> Literal["theoretical_retrieval", "safety_check", "treatment_retrieval", "conversation_memory"]:
    """
    Routing logic after router node:
    1. Check if awaiting treatment confirmation from previous disease_conclusion
       - If awaiting and user says YES (from LLM) -> treatment_retrieval
       - If awaiting and user says NO (from LLM) -> conversation_memory (ask if need other help, then END)
    2. Otherwise, route based on query_nature:
       - theoretical -> theoretical_retrieval
       - personal -> safety_check
    """
    import logging
    logger = logging.getLogger(__name__)
    
    awaiting_treatment = state.get("awaiting_treatment_confirmation", False)
    
    if awaiting_treatment:
        # Check LLM classification result
        wants_treatment = state.get("wants_treatment", False)
        
        if wants_treatment:
            logger.info("[ROUTING] User wants treatment (LLM classified) -> treatment_retrieval")
            state["user_wants_treatment"] = True
            return "treatment_retrieval"
        else:
            # User doesn't want treatment - offer other help and go to conversation_memory
            logger.info("[ROUTING] User doesn't want treatment (LLM classified) -> conversation_memory (offer other help then END)")
            language = state.get("user_language", "vi")
            if language in ["vi", "vn"]:
                state["answer"] = "Được rồi. Bạn có muốn tôi hỗ trợ gì thêm về vấn đề tâm lý không?"
            else:
                state["answer"] = "Okay. Is there anything else I can help you with?"
            # Reset awaiting flag
            state["awaiting_treatment_confirmation"] = False
            return "conversation_memory"
    
    # Normal routing based on query nature
    query_nature = state.get("query_nature", "personal")
    
    if query_nature == "theoretical":
        logger.info("[ROUTING] Theoretical question - direct to theoretical retrieval")
        return "theoretical_retrieval"
    
    # Personal question - go through safety check + diagnostic flow
    logger.info("[ROUTING] Personal question - go through safety check + diagnostic flow")
    return "safety_check"


def route_after_slot_filling(state: KGState) -> Literal["query_rewriter", "request_more_info"]:
    """
    Routing logic sau khi slot filling:
    - Nếu đủ slots -> query_rewriter (rewrite query trước khi assessment)
    - Nếu thiếu slots -> request_more_info (hỏi thêm)
    """
    has_sufficient = state.get("has_sufficient_slots", False)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[ROUTING] route_after_slot_filling: has_sufficient_slots = {has_sufficient}")
    logger.info(f"[ROUTING] has_sufficient_slots in state.keys(): {'has_sufficient_slots' in state}")
    logger.info(f"[ROUTING] All slot-related keys: {[k for k in state.keys() if 'slot' in k.lower()]}")
    logger.info(f"[ROUTING] Direct access state['has_sufficient_slots']: {state.get('has_sufficient_slots', 'KEY NOT FOUND')}")
    logger.info(f"[ROUTING] Will route to: {'query_rewriter' if has_sufficient else 'request_more_info'}")
    
    if has_sufficient:
        return "query_rewriter"
    else:
        return "request_more_info"


def route_after_query_rewriter(state: KGState) -> Literal["assessment"]:
    """
    After query rewriting, always go to assessment to check normal vs disorder.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[ROUTING] After query_rewriter -> assessment")
    return "assessment"


def route_after_slot_filling_simplified(state: KGState) -> Literal["query_rewriter", "request_more_info"]:
    """
    Simplified routing: Check if we have enough slots, then go directly to diagnostic retrieval.
    Removed assessment/screening as they were not providing value.
    
    Routes:
    - Sufficient slots → query_rewriter (proceed to diagnostic flow)
    - Insufficient slots → request_more_info (request more information)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from src.rag.utils.slots import has_sufficient_slots
    
    slots = state.get("slots", {})
    # FIXED: has_sufficient_slots returns tuple (is_sufficient, required_missing, differential_missing)
    is_sufficient, required_missing, differential_missing = has_sufficient_slots(slots)
    
    logger.info(f"[ROUTING] route_after_slot_filling_simplified: is_sufficient = {is_sufficient}")
    logger.info(f"[ROUTING]   Required missing: {required_missing}")
    logger.info(f"[ROUTING]   Differential missing: {differential_missing}")
    
    if is_sufficient:
        logger.info("[ROUTING] ✅ Sufficient slots → query_rewriter (diagnostic flow)")
        return "query_rewriter"
    else:
        logger.info(f"[ROUTING] ❌ Insufficient slots → request_more_info")
        logger.info(f"[ROUTING]    Missing: {required_missing}")
        return "request_more_info"


def route_after_assessment(state: KGState) -> Literal["normal_coping_retrieval", "adjustment_retrieval", "diagnostic_retrieval"]:
    """
    Route after assessment based on normal_stress and adjustment_reaction scores.
    
    Routing Logic (Updated):
    - If any score > 60: -> diagnostic_retrieval (severe symptoms need diagnosis)
    - If both scores < 60: choose higher score category
      * normal_stress_score higher: -> normal_coping_retrieval
      * adjustment_reaction_score higher: -> adjustment_retrieval
    """
    import logging
    logger = logging.getLogger(__name__)
    
    normal_stress_score = state.get("normal_stress_score", 0.0)
    adjustment_reaction_score = state.get("adjustment_reaction_score", 0.0)
    assessment_category = state.get("assessment_category", "possible_disorder")
    
    logger.info(f"[ROUTING] route_after_assessment:")
    logger.info(f"  normal_stress_score: {normal_stress_score:.2f}")
    logger.info(f"  adjustment_reaction_score: {adjustment_reaction_score:.2f}")
    logger.info(f"  assessment_category: {assessment_category}")
    
    # Route based on category determined in assessment node
    if assessment_category == "normal_response":
        logger.info("[ROUTING] ✅ Normal stress response (score < 60) -> normal_coping_retrieval")
        return "normal_coping_retrieval"
    elif assessment_category == "adjustment_reaction":
        logger.info("[ROUTING] ✅ Adjustment reaction (score < 60) -> adjustment_retrieval")
        return "adjustment_retrieval"
    else:
        logger.info("[ROUTING] ⚠️ Possible disorder (score > 60 or low match) -> diagnostic_retrieval")
        return "diagnostic_retrieval"


def route_after_crisis_follow_up(state: KGState) -> Literal["crisis_escalation", "crisis_contextual_support", "crisis_gentle_persistence", "crisis_to_normal_transition"]:
    """
    Route after crisis follow-up classifier based on user response classification.
    
    Classifications:
    - immediate_danger: User confirms immediate danger -> Escalate
    - seeking_help: User wants support -> Contextual support with coping
    - declining_help: User defensive -> Gentle persistence (if count < 2) or support anyway
    - de_escalated: User calmer -> Transition to normal flow with monitoring
    """
    classification = state.get("crisis_follow_up_classification", "seeking_help")
    crisis_response_count = state.get("crisis_response_count", 0)
    
    logger.info(f"[CRISIS ROUTING] Classification: {classification}, Count: {crisis_response_count}")
    
    if classification == "immediate_danger":
        logger.critical("[CRISIS ROUTING] 🔴 Immediate danger → crisis_escalation")
        return "crisis_escalation"
    
    elif classification == "seeking_help":
        logger.info("[CRISIS ROUTING] 💚 Seeking help → crisis_contextual_support")
        return "crisis_contextual_support"
    
    elif classification == "declining_help":
        if crisis_response_count < 2:
            logger.warning("[CRISIS ROUTING] ⚠️ Declining help (try again) → crisis_gentle_persistence")
            return "crisis_gentle_persistence"
        else:
            logger.warning("[CRISIS ROUTING] ⚠️ Declining help (max tries) → crisis_contextual_support")
            return "crisis_contextual_support"
    
    elif classification == "de_escalated":
        logger.info("[CRISIS ROUTING] ✅ De-escalated → crisis_to_normal_transition")
        return "crisis_to_normal_transition"
    
    # Fallback
    logger.warning(f"[CRISIS ROUTING] Unknown classification: {classification}. Defaulting to contextual support.")
    return "crisis_contextual_support"


def route_after_screening(state: KGState) -> Literal["query_rewriter", "normal_coping_retrieval", "adjustment_retrieval"]:
    """
    Route after diagnostic screening based on screening results.
    
    Screening Results:
    - disorder_suspected: Go to full diagnostic flow (query_rewriter → diagnostic_retrieval)
    - subclinical: Go to adjustment support (monitoring + coping)
    - non_clinical: Go to normal coping strategies
    
    This routing happens AFTER universal screening, not before.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    screening_result = state.get("screening_result", "disorder_suspected")
    severity_level = state.get("severity_level", "moderate")
    
    logger.info(f"[ROUTING] route_after_screening: screening_result = {screening_result}, severity = {severity_level}")
    
    if screening_result == "disorder_suspected":
        logger.info("[ROUTING] Disorder suspected → full diagnostic flow (query_rewriter)")
        return "query_rewriter"
    
    elif screening_result == "subclinical":
        logger.info("[ROUTING] Subclinical level → adjustment support")
        return "adjustment_retrieval"
    
    else:  # non_clinical
        logger.info("[ROUTING] Non-clinical → normal coping strategies")
        return "normal_coping_retrieval"


def route_after_disease_conclusion(state: KGState) -> Literal["treatment_retrieval", "graph_retrieval"]:
    """
    Routing logic after disease conclusion:
    - If detected_disease exists AND confidence > 0.8:
      * Set awaiting_treatment_confirmation = True
      * Ask user if they want treatment suggestions
      * Go to conversation_memory -> END (wait for user response)
    - If detected_disease is empty OR confidence <= 0.8:
      * Go to graph_retrieval (fallback)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    detected_disease = state.get("detected_disease", "")
    diagnostic_confidence = state.get("diagnostic_confidence", 0.0)
    
    if detected_disease and diagnostic_confidence > 0.75:
        # Disease detected with high confidence - ask for treatment confirmation
        logger.info(f"[ROUTING] Disease detected: '{detected_disease}' (confidence={diagnostic_confidence:.2f}) -> Ask treatment confirmation -> conversation_memory -> END")
        return "conversation_memory"
    else:
        # No disease or low confidence - fallback to graph
        if detected_disease:
            logger.info(f"[ROUTING] Disease detected but low confidence ({diagnostic_confidence:.2f} <= 0.75) -> graph_retrieval")
        else:
            logger.info("[ROUTING] No disease detected -> graph_retrieval")
        return "graph_retrieval"


def build_kg_graph():
    """
    Build Knowledge Graph RAG workflow with conversation memory support
    
    Workflow:
    1. translate_question -> Detect language (VI/EN), translate to EN if needed
    2. classify_query -> LLM classify query type (follow_up, topic_change, off_topic)
    3. route_after_classify_query -> Route based on query type:
       3a. If off_topic -> not_mental_health (reject)
       3b. If follow_up/topic_change -> safety_check
    4. safety_check -> Check if mental health related and risk level (with conditional enhancement)
    5. route_after_safety_check -> Route based on safety_check results:
       5a. If high-risk -> crisis_response -> END
       5b. If not mental health -> not_mental_health -> END  
       5c. If safe & relevant -> slot_filling -> route_after_slot_filling
    6. route_after_slot_filling:
       6a. If REQUIRED slots insufficient -> request_more_info -> END
       6b. If REQUIRED slots sufficient -> query_rewriter -> retrieval -> answer -> conversation_memory -> END
    
    Conversation Memory:
    - query_similarity_check: Check if query is follow-up, topic_change, or off_topic
    - classify_query: LLM classify query type (only if similarity < 0.8)
    - safety_check: Conditional enhancement based on query_type
    - query_rewriter: Uses last 3 buffer pairs + summary + slots to rewrite query
    - retrieval: Uses rewritten query (with slots + conversation context)
    - answer: Enhanced with chunks + slots + last 3 buffer pairs + summary
    - conversation_memory: Update buffer + summary, handle topic change
    
    Slot filling (after safety check passes):
    - Extract structured information (emotion, trigger, duration, etc.)
    - Separate into REQUIRED vs OPTIONAL missing slots
    - Check if REQUIRED slots are sufficiently filled (at least 5/8)
    
    Two-phase follow-up strategy:
    - Phase 1 (Before retrieval): If REQUIRED slots insufficient → request_more_info
      * Only ask about REQUIRED_SLOTS (emotion, mood, intensity, trigger, duration, impact, need, stress)
      * User must complete these before retrieval happens
    
    - Phase 2 (After answer): If REQUIRED slots sufficient → proceed with answer
      * Generate answer from retrieval
      * Append optional follow-up questions at the end (e.g., sleep, coping, support)
      * These don't block the answer, just gather additional context for future turns
    
    Query Rewriting (separate node):
    - Runs after slot filling when REQUIRED slots are sufficient
    - Combines: filled slots + last 3 conversation pairs + summary context
    - Example: "Tôi buồn quá" → "Tôi đang cảm thấy rất buồn trong thời gian gần đây"
    - Also runs for follow-up messages
    - Improves retrieval quality by providing rich context
    - Rewritten query is used by both dense_retrieval and graph_retrieval nodes
    
    Translation logic:
    - Vietnamese input: VI -> EN (processing) -> VI (output)
    - English input: EN (no translation) -> EN (output)
    
    Graph retrieval integrates:
    - Encode query -> Milvus search -> Rerank -> Expand subgraph
    - All async for non-blocking execution
    
    Note: hybrid_retrieval (graph + dense parallel) is available but commented out for now
    """
    builder = StateGraph(KGState)

    # Add nodes (all async now)
    builder.add_node("translate_question", translate_question_node)
    builder.add_node("classify_type_query", query_type_classifier_node)
    builder.add_node("router", router_node)  # NEW NODE
    builder.add_node("safety_check", safety_check_node)
    builder.add_node("slot_filling", slot_filling_node)  # Chạy sau safety_check
    builder.add_node("assessment", assessment_node)  # Assess severity only (no binary classification)
    
    # Crisis response nodes (NEW: Multi-stage adaptive crisis system)
    builder.add_node("crisis_response", crisis_response_node)  # Legacy (backward compat)
    builder.add_node("crisis_immediate_response", crisis_immediate_response_node)  # Stage 1
    builder.add_node("crisis_follow_up_classifier", crisis_follow_up_classifier_node)  # Stage 2
    builder.add_node("crisis_escalation", crisis_escalation_node)  # Stage 3a
    builder.add_node("crisis_contextual_support", crisis_contextual_support_node)  # Stage 3b
    builder.add_node("crisis_gentle_persistence", crisis_gentle_persistence_node)  # Stage 3c
    builder.add_node("crisis_to_normal_transition", crisis_to_normal_transition_node)  # Stage 3d
    
    builder.add_node("not_mental_health", not_mental_health_node)
    builder.add_node("request_more_info", request_more_info_node)  # Hỏi thêm nếu thiếu slots
    builder.add_node("query_rewriter", query_rewriter_node)  # Rewrite query với slots + conversation
    
    # Assessment-based retrieval nodes (NEW)
    builder.add_node("normal_coping_retrieval", normal_coping_retrieval_node)  # Normal stress content
    builder.add_node("adjustment_retrieval", adjustment_retrieval_node)  # Adjustment reaction content
    
    # Diagnostic and treatment nodes
    builder.add_node("diagnostic_retrieval", diagnostic_retrieval_node)
    builder.add_node("disease_conclusion", disease_conclusion_node)
    builder.add_node("treatment_retrieval", treatment_retrieval_node)
    builder.add_node("answer_with_treatment", answer_with_treatment_node)

    # Theoretical retrieval and answer nodes
    builder.add_node("theoretical_retrieval", theoretical_retrieval_node)
    builder.add_node("answer_with_theoretical", answer_with_theoretical_node)
    
    # Graph retrieval and answer nodes
    builder.add_node("graph_retrieval", graph_retrieval_node)
    builder.add_node("answer_with_graph", answer_with_graph_node)
    
    # Legacy dense retrieval (kept for backward compatibility)
    builder.add_node("conversation_memory", conversation_memory_node)

    # Entry point - start with translation
    builder.set_entry_point("translate_question")
    
    # Sequential flow: translate -> classify_query (direct to LLM, no embedding similarity check)
    builder.add_edge("translate_question", "classify_type_query")
    
    # Conditional routing after classify_query
    builder.add_conditional_edges(
        "classify_type_query",
        route_after_classify_query,
        {
            "router": "router",  # follow_up or topic_change
            "not_mental_health": "not_mental_health",  # off_topic -> reject ngay
        },
    )

    # NEW: Conditional routing after router (handles treatment confirmation + personal/theoretical)
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "theoretical_retrieval": "theoretical_retrieval",  # theoretical -> skip safety + slots
            "safety_check": "safety_check",  # personal -> full diagnostic flow
            "treatment_retrieval": "treatment_retrieval",  # User wants treatment
            "conversation_memory": "conversation_memory",  # User doesn't want treatment -> ask if need other help -> END
        },
    )

    # Conditional routing after safety check
    builder.add_conditional_edges(
        "safety_check",
        route_after_safety_check,
        {
            "crisis_immediate_response": "crisis_immediate_response",  # NEW: Multi-stage crisis
            "crisis_escalation": "crisis_escalation",  # Re-escalation case
            "crisis_to_normal_transition": "crisis_to_normal_transition",  # Safe after recent crisis
            "slot_filling": "slot_filling",  # Personal questions -> full diagnostic flow
        },
    )
    
    # Crisis flow: immediate_response -> classifier (waits for next user input)
    # Note: done=False allows user to respond, next turn re-enters at safety_check which routes to classifier
    builder.add_edge("crisis_immediate_response", END)  # Temporary: wait for user response
    
    # Crisis follow-up classifier routes based on user response
    builder.add_conditional_edges(
        "crisis_follow_up_classifier",
        route_after_crisis_follow_up,
        {
            "crisis_escalation": "crisis_escalation",
            "crisis_contextual_support": "crisis_contextual_support",
            "crisis_gentle_persistence": "crisis_gentle_persistence",
            "crisis_to_normal_transition": "crisis_to_normal_transition",
        },
    )
    
    # All crisis stage nodes return to END (done=False allows continuation)
    builder.add_edge("crisis_escalation", END)
    builder.add_edge("crisis_contextual_support", END)
    builder.add_edge("crisis_gentle_persistence", END)
    builder.add_edge("crisis_to_normal_transition", END)
    
    # Legacy crisis response (backward compat)
    builder.add_edge("crisis_response", END)
    
    # Theoretical flow: theoretical_retrieval -> answer_with_theoretical -> conversation_memory
    builder.add_edge("theoretical_retrieval", "answer_with_theoretical")
    builder.add_edge("answer_with_theoretical", "conversation_memory")

    # Non-relevant queries exit directly
    builder.add_edge("not_mental_health", END)

    # Conditional routing after slot filling (SIMPLIFIED - no assessment/screening)
    builder.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling_simplified,
        {
            "query_rewriter": "query_rewriter",  # Đủ slots → query rewriter → diagnostic
            "request_more_info": "request_more_info",  # Thiếu slots → hỏi thêm
        },
    )

    # Request more info -> conversation_memory -> END (save Q&A pair to buffer)
    builder.add_edge("request_more_info", "conversation_memory")

    # UPDATED FLOW: query_rewriter → assessment → route based on scores
    builder.add_edge("query_rewriter", "assessment")
    
    # Conditional routing after assessment (check normal vs disorder)
    builder.add_conditional_edges(
        "assessment",
        route_after_assessment,
        {
            "normal_coping_retrieval": "normal_coping_retrieval",  # Normal stress
            "adjustment_retrieval": "adjustment_retrieval",  # Adjustment reaction
            "diagnostic_retrieval": "diagnostic_retrieval",  # Possible disorder
        },
    )
    
    # Normal coping flow: normal_coping_retrieval -> answer_with_graph -> conversation_memory
    builder.add_edge("normal_coping_retrieval", "answer_with_graph")
    
    # Adjustment flow: adjustment_retrieval -> answer_with_graph -> conversation_memory
    builder.add_edge("adjustment_retrieval", "answer_with_graph")

    # DIAGNOSTIC FLOW: diagnostic_retrieval → disease_conclusion (auto)
    builder.add_edge("diagnostic_retrieval", "disease_conclusion")  # Auto transition
    
    # Route after disease conclusion based on whether disease was detected
    builder.add_conditional_edges(
        "disease_conclusion",
        route_after_disease_conclusion,
        {
            "conversation_memory": "conversation_memory",  # Có bệnh -> hỏi xác nhận -> END (chờ user trả lời)
            "graph_retrieval": "graph_retrieval",  # Không bệnh -> graph fallback
        },
    )
    
    # Treatment flow: treatment_retrieval -> answer_with_treatment -> conversation_memory
    builder.add_edge("treatment_retrieval", "answer_with_treatment")
    builder.add_edge("answer_with_treatment", "conversation_memory")
    
    # Graph flow: graph_retrieval -> answer_with_graph -> conversation_memory
    builder.add_edge("graph_retrieval", "answer_with_graph")
    builder.add_edge("answer_with_graph", "conversation_memory")
    
    # All flows converge at conversation_memory -> END
    builder.add_edge("conversation_memory", END)


    # Compile with PostgreSQL checkpointer for state persistence
    checkpointer = get_checkpointer()
    logger.info("Compiling workflow graph with PostgreSQL checkpointer")
    return builder.compile(checkpointer=checkpointer)

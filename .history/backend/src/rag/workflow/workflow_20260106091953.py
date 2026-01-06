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
from .graph_nodes.diagnostic_screening import diagnostic_screening_node

logger = logging.getLogger(__name__)


def route_after_safety_check(state: KGState) -> Literal["crisis_response", "slot_filling"]:
    """
    Routing logic sau khi check safety:
    - Nếu high-risk -> crisis_response
    - Nếu safe -> slot_filling (personal questions đã được filter trước đó)
    """
    if state.get("is_high_risk", False):
        return "crisis_response"
    
    # Safe personal question - go through full diagnostic flow
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


def route_after_slot_filling(state: KGState) -> Literal["assessment", "request_more_info"]:
    """
    Routing logic sau khi slot filling:
    - Nếu đủ slots -> assessment (NEW: assess normal vs disorder)
    - Nếu thiếu slots -> request_more_info (hỏi thêm)
    """
    has_sufficient = state.get("has_sufficient_slots", False)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[ROUTING] route_after_slot_filling: has_sufficient_slots = {has_sufficient}")
    logger.info(f"[ROUTING] has_sufficient_slots in state.keys(): {'has_sufficient_slots' in state}")
    logger.info(f"[ROUTING] All slot-related keys: {[k for k in state.keys() if 'slot' in k.lower()]}")
    logger.info(f"[ROUTING] Direct access state['has_sufficient_slots']: {state.get('has_sufficient_slots', 'KEY NOT FOUND')}")
    logger.info(f"[ROUTING] Will route to: {'assessment' if has_sufficient else 'request_more_info'}")
    
    if has_sufficient:
        return "assessment"
    else:
        return "request_more_info"


def route_after_slot_filling_simplified(state: KGState) -> Literal["query_rewriter", "request_more_info"]:
    """
    Simplified routing: Check if we have enough slots, then go directly to diagnostic retrieval.
    Removed assessment/screening as they were not providing value.
    
    Routes:
    - Sufficient slots → query_rewriter → diagnostic_retrieval
    - Insufficient slots → request_more_info
    """
    import logging
    logger = logging.getLogger(__name__)
    
    from src.rag.utils.slots import has_sufficient_slots
    
    slots = state.get("slots", {})
    
    if has_sufficient_slots(slots):
        logger.info("[ROUTING] Sufficient slots → query_rewriter → diagnostic_retrieval")
        return "query_rewriter"
    else:
        logger.info("[ROUTING] Insufficient slots → request_more_info")
        return "request_more_info"


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
    - If detected_disease exists (not empty):
      * Set awaiting_treatment_confirmation = True
      * Ask user if they want treatment suggestions
      * Go to conversation_memory -> END (wait for user response)
    - If detected_disease is empty:
      * Go to graph_retrieval (fallback)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    detected_disease = state.get("detected_disease", "")
    
    if detected_disease:
        # Disease detected - ask for treatment confirmation
        logger.info(f"[ROUTING] Disease detected: '{detected_disease}' -> Ask treatment confirmation -> conversation_memory -> END")
        return "conversation_memory"
    else:
        # No disease - fallback to graph
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
    builder.add_node("diagnostic_screening", diagnostic_screening_node)  # NEW: Universal disorder screening
    builder.add_node("crisis_response", crisis_response_node)
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
            "crisis_response": "crisis_response",
            "slot_filling": "slot_filling",  # Personal questions -> full diagnostic flow
        },
    )
    # Theoretical flow: theoretical_retrieval -> answer_with_theoretical -> conversation_memory
    builder.add_edge("theoretical_retrieval", "answer_with_theoretical")
    builder.add_edge("answer_with_theoretical", "conversation_memory")

    # Crisis and non-relevant queries exit directly
    builder.add_edge("crisis_response", END)
    builder.add_edge("not_mental_health", END)

    # Conditional routing after slot filling (UPDATED)
    builder.add_conditional_edges(
        "slot_filling",
        route_after_slot_filling,
        {
            "assessment": "assessment",  # NEW: Đủ slots -> assessment
            "request_more_info": "request_more_info",  # Thiếu slots -> hỏi thêm
        },
    )
    
    # NEW: Conditional routing after assessment (ALL cases → diagnostic_screening)
    builder.add_conditional_edges(
        "assessment",
        route_after_assessment,
        {
            "diagnostic_screening": "diagnostic_screening",  # NEW: Universal screening (to be enabled)
            "query_rewriter": "query_rewriter",  # Temporary fallback (current flow)
        },
    )
    
    # NEW: Conditional routing after diagnostic_screening
    builder.add_conditional_edges(
        "diagnostic_screening",
        route_after_screening,
        {
            "query_rewriter": "query_rewriter",  # Disorder suspected → diagnostic flow
            "adjustment_retrieval": "adjustment_retrieval",  # Subclinical → adjustment support
            "normal_coping_retrieval": "normal_coping_retrieval",  # Non-clinical → coping strategies
        },
    )

    # Request more info exits directly (no retrieval)
    builder.add_edge("request_more_info", END)
    
    # NEW: Normal/adjustment flows -> answer_with_graph -> conversation_memory -> END
    builder.add_edge("normal_coping_retrieval", "answer_with_graph")
    builder.add_edge("adjustment_retrieval", "answer_with_graph")

    # NEW DIAGNOSTIC FLOW: query_rewriter -> diagnostic_retrieval -> disease_conclusion (auto)
    builder.add_edge("query_rewriter", "diagnostic_retrieval")
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

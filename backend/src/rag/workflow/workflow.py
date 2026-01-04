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

def route_after_personal_theoretical(state: KGState) -> Literal["theoretical_retrieval", "safety_check"]:
    """
    Routing logic sau khi classify personal/theoretical:
    - Nếu theoretical -> theoretical_retrieval (skip safety + slot filling)
    - Nếu personal -> safety_check (full diagnostic flow)
    """
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


def route_after_assessment(state: KGState) -> Literal["normal_coping_retrieval", "adjustment_retrieval", "query_rewriter"]:
    """
    NEW ROUTING: Route based on assessment category.
    
    Routes:
    - normal_response → normal_coping_retrieval (focus coping, NOT disorder)
    - adjustment_reaction → adjustment_retrieval (focus adjustment, NOT disorder)
    - possible_disorder / likely_disorder → query_rewriter → diagnostic_retrieval (current flow)
    - insufficient_info → query_rewriter (fallback to diagnostic flow)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    category = state.get("assessment_category", "possible_disorder")
    
    logger.info(f"[ROUTING] route_after_assessment: category = {category}")
    
    if category == "normal_response":
        logger.info("[ROUTING] Normal response detected → normal_coping_retrieval")
        return "normal_coping_retrieval"
    elif category == "adjustment_reaction":
        logger.info("[ROUTING] Adjustment reaction detected → adjustment_retrieval")
        return "adjustment_retrieval"
    else:
        # possible_disorder, likely_disorder, or insufficient_info → proceed to diagnostic flow
        logger.info(f"[ROUTING] {category} → diagnostic flow (query_rewriter)")
        return "query_rewriter"


def route_after_disease_conclusion(state: KGState) -> Literal["treatment_retrieval", "graph_retrieval"]:
    """
    Routing logic after disease conclusion:
    - If detected_disease exists (not empty) -> treatment_retrieval (có bệnh, lấy hướng dẫn điều trị)
    - If detected_disease is empty -> graph_retrieval (không bệnh, dùng graph fallback)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    detected_disease = state.get("detected_disease", "")
    
    if detected_disease:
        logger.info(f"[ROUTING] Disease detected: '{detected_disease}' -> treatment_retrieval")
        return "treatment_retrieval"
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
    builder.add_node("assessment", assessment_node)  # NEW: Assess normal vs disorder
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

    # NEW: Conditional routing after personal/theoretical classification
    builder.add_conditional_edges(
        "router",
        route_after_personal_theoretical,
        {
            "theoretical_retrieval": "theoretical_retrieval",  # theoretical -> skip safety + slots
            "safety_check": "safety_check",  # personal -> full diagnostic flow
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
    # Theoretical flow: theoretical_retrieval -> answer_with_theoretical -> END
    builder.add_edge("theoretical_retrieval", "answer_with_theoretical")
    builder.add_edge("answer_with_theoretical", "conversation_memory")
    builder.add_edge("conversation_memory", END)

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
    
    # NEW: Conditional routing after assessment
    builder.add_conditional_edges(
        "assessment",
        route_after_assessment,
        {
            "normal_coping_retrieval": "normal_coping_retrieval",  # Normal stress
            "adjustment_retrieval": "adjustment_retrieval",  # Adjustment reaction
            "query_rewriter": "query_rewriter",  # Possible/likely disorder -> diagnostic flow
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
            "treatment_retrieval": "treatment_retrieval",  # Có bệnh -> lấy guidance
            "graph_retrieval": "graph_retrieval",  # Không bệnh -> graph fallback
        },
    )
    
    # Treatment flow: treatment_retrieval -> answer_with_treatment -> END
    builder.add_edge("treatment_retrieval", "answer_with_treatment")
    builder.add_edge("answer_with_treatment", "conversation_memory")
    builder.add_edge("conversation_memory", END)
    
    # Graph flow: graph_retrieval -> answer_with_graph -> END
    builder.add_edge("graph_retrieval", "answer_with_graph")
    builder.add_edge("answer_with_graph", "conversation_memory")
    builder.add_edge("conversation_memory", END)


    # Compile with PostgreSQL checkpointer for state persistence
    checkpointer = get_checkpointer()
    logger.info("Compiling workflow graph with PostgreSQL checkpointer")
    return builder.compile(checkpointer=checkpointer)

from typing import TypedDict, List, Dict, Any, Optional


class KGState(TypedDict):
    question: str
    original_question: str
    user_language: str
    is_mental_health_related: bool  
    is_high_risk: bool  
    query_embedding: List[float]
    anchors: List[Dict[str, Any]]
    nodes: List[Any]
    rels: List[Any]
    graph_context: str
    dense_context: str
    answer: str
    done: bool
    
    # Slot Filling Data
    slots: Optional[Dict[str, Any]]
    missing_slots: Optional[List[str]]
    relevant_missing_slots: Optional[List[str]]
    follow_up_questions: Optional[List[str]]
    
    # Timing tracking for parallel execution
    parallel_start_time: Optional[float]  # Timestamp when parallel execution starts

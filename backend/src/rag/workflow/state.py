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
    
    # Conversation Memory
    conversation_buffer: Optional[List[Dict[str, str]]]  # List of Q&A pairs: [{"user": "...", "bot": "..."}]
    summary_context: Optional[str]  # Summarized older conversation pairs
    previous_follow_up_questions: Optional[List[str]]  # Follow-up questions from previous turn
    
    # Query Classification (for conditional enhancement)
    query_type: Optional[str]  # "follow_up" | "topic_change" | "off_topic"
    should_enhance_query: Optional[bool]  # Whether to enhance query with buffer + summary
    query_similarity: Optional[float]  # Similarity score between query and conversation context
    is_topic_change: Optional[bool]  # Flag for topic change detection
    is_off_topic: Optional[bool]  # Flag for off-topic detection
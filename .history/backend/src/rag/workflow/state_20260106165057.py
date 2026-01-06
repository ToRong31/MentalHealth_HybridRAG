from typing import List, Dict, Any, Optional
try:
    from typing_extensions import TypedDict
except ImportError:
    from typing import TypedDict


class KGState(TypedDict, total=False):
    """
    State definition for Knowledge Graph RAG workflow
    
    Note: total=False makes all fields optional by default,
    allowing LangGraph to properly merge state updates across nodes.
    """
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
    slots: Dict[str, Any] 
    missing_slots: List[str]
    relevant_missing_slots: List[str]
    follow_up_questions: List[str]
    has_sufficient_slots: bool  # Whether REQUIRED slots are sufficiently filled
    required_missing_slots: List[str]  # List of missing REQUIRED slots
    rewritten_query: str  # Query rewritten with slots + conversation context
    optional_follow_up_questions: List[str]  # Optional questions to ask in answer (not blocking)
    
    # Timing tracking for parallel execution
    parallel_start_time: float  # Timestamp when parallel execution starts
    
    # Conversation Memory
    conversation_buffer: List[Dict[str, str]]  # List of Q&A pairs: [{"user": "...", "bot": "..."}]
    summary_context: str  # Summarized older conversation pairs
    previous_follow_up_questions: List[str]  # Follow-up questions from previous turn
    
    # Query Classification (for conditional enhancement)
    query_type: str  # "follow_up" | "topic_change" | "off_topic"
    query_nature: str  # "personal" | "theoretical"
    should_enhance_query: bool  # Whether to enhance query with buffer + summary
    query_similarity: float  # Similarity score between query and conversation context
    is_topic_change: bool  # Flag for topic change detection
    is_off_topic: bool  # Flag for off-topic detection
    
    # Diagnostic fields
    diagnostic_chunks: str  # Chunks from diagnostic retrieval
    diagnostic_diseases: List[str]  # List of diseases from diagnostic retrieval
    detected_disease: str  # Disease name detected
    diagnostic_confidence: float  # Confidence score 0-1
    diagnostic_reasoning: str  # LLM reasoning for diagnosis
    disease_detected: List[str]  # List of confirmed diseases (when confidence high enough)

    theoretical_chunks: str  # Chunks from theoretical retrieval
    theoretical_metadata: Dict[str, Any]  # Metadata from theoretical retrieval
    
    # Treatment fields
    awaiting_treatment_confirmation: bool  # Waiting for user to confirm treatment
    wants_treatment: bool  # LLM classification result: user wants treatment or not
    treatment_chunks: List[str]  # Treatment chunks retrieved by disease
    treatment_node_ids: List[int]  # Node IDs of treatment chunks
    user_wants_treatment: bool  # User confirmed wanting treatment
    
    # Routing flags
    needs_apology_prefix: bool  # Flag to add apology prefix for low confidence diagnosis
    
    # Conversation ID
    conversation_id: str
    user_id: str


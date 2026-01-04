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
    has_sufficient_slots: Optional[bool]  # Whether REQUIRED slots are sufficiently filled
    required_missing_slots: Optional[List[str]]  # List of missing REQUIRED slots
    rewritten_query: Optional[str]  # Query rewritten with slots + conversation context
    optional_follow_up_questions: Optional[List[str]]  # Optional questions to ask in answer (not blocking)
    
    # Timing tracking for parallel execution
    parallel_start_time: Optional[float]  # Timestamp when parallel execution starts
    
    # Conversation Memory
    conversation_buffer: Optional[List[Dict[str, str]]]  # List of Q&A pairs: [{"user": "...", "bot": "..."}]
    summary_context: Optional[str]  # Summarized older conversation pairs
    previous_follow_up_questions: Optional[List[str]]  # Follow-up questions from previous turn
    
    # Query Classification (for conditional enhancement)
    query_type: Optional[str]  # "follow_up" | "topic_change" | "off_topic"
    query_nature: Optional[str]  # "personal" | "theoretical"
    should_enhance_query: Optional[bool]  # Whether to enhance query with buffer + summary
    query_similarity: Optional[float]  # Similarity score between query and conversation context
    is_topic_change: Optional[bool]  # Flag for topic change detection
    is_off_topic: Optional[bool]  # Flag for off-topic detection
    
    # Diagnostic fields
    diagnostic_chunks: Optional[str]  # Chunks from diagnostic retrieval
    diagnostic_diseases: Optional[List[str]]  # List of diseases from diagnostic retrieval
    detected_disease: Optional[str]  # Disease name detected
    diagnostic_confidence: Optional[float]  # Confidence score 0-1
    diagnostic_reasoning: Optional[str]  # LLM reasoning for diagnosis
    disease_detected: Optional[List[str]]  # List of confirmed diseases (when confidence high enough)

    theoretical_chunks: Optional[str]  # Chunks from theoretical retrieval
    theoretical_metadata: Optional[Dict[str, Any]]  # Metadata from theoretical retrieval
    
    # Treatment fields
    awaiting_treatment_confirmation: Optional[bool]  # Waiting for user to confirm treatment
    treatment_chunks: Optional[List[str]]  # Treatment chunks retrieved by disease
    treatment_node_ids: Optional[List[int]]  # Node IDs of treatment chunks
    user_wants_treatment: Optional[bool]  # User confirmed wanting treatment
    
    # Routing flags
    needs_apology_prefix: Optional[bool]  # Flag to add apology prefix for low confidence diagnosis
    
    # Assessment fields (Normal vs Disorder Classification)
    assessment_category: Optional[str]  # "normal_response" | "adjustment_reaction" | "possible_disorder" | "likely_disorder"
    assessment_explanation: Optional[str]  # Vietnamese explanation of assessment
    assessment_confidence: Optional[float]  # Confidence score 0-1 for assessment


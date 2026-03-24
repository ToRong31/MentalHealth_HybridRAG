"""
Router Node
Handles both personal/theoretical classification and treatment confirmation classification
"""
from typing import Dict, Any
import logging

from src.rag.llm.answer_nodes.router import router

logger = logging.getLogger(__name__)


async def router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node: Router that handles multiple classification tasks:
    1. If awaiting_treatment_confirmation=True: Classify if user wants treatment
    2. Otherwise: Classify query nature (personal or theoretical)
    
    Args:
        state: State dict with question, query_type, conversation_buffer, summary_context, 
               awaiting_treatment_confirmation, detected_disease
    
    Returns:
        Updated state with query_nature/wants_treatment and reasoning
    """
    question = state.get("question", "")
    awaiting_treatment = state.get("awaiting_treatment_confirmation", False)
    
    if awaiting_treatment:
        # User is responding to treatment question - classify treatment confirmation
        detected_disease = state.get("detected_disease", "")
        buffer = state.get("conversation_buffer", [])
        summary = state.get("summary_context", "")
        
        logger.info("🔄 Router: Classifying treatment confirmation")
        
        result = await router(
            question=question,
            conversation_buffer=buffer,
            summary_context=summary,
            awaiting_treatment_confirmation=True,
            detected_disease=detected_disease
        )
        
        # Update state with result
        state.update(result)
        
        wants_treatment = result.get("wants_treatment", False)
        reasoning = result.get("reasoning", "")
        
        logger.info(f"Treatment confirmation: wants_treatment={wants_treatment} - {reasoning}")
        
    else:
        # Normal routing - classify personal/theoretical
        query_type = state.get("query_type", "follow_up")
        buffer = state.get("conversation_buffer", [])
        summary = state.get("summary_context", "")
        
        logger.info("🔄 Router: Classifying query nature (personal/theoretical)")
        
        result = await router(
            question=question,
            query_type=query_type,
            conversation_buffer=buffer,
            summary_context=summary,
            awaiting_treatment_confirmation=False
        )
        
        # Update state with result
        state.update(result)
        
        query_nature = result.get("query_nature", "personal")
        reasoning = result.get("reasoning", "")
        
        logger.info(f"Query nature: {query_nature} - {reasoning}")
    
    return state

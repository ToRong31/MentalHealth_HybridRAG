"""
Diagnostic Check Node
Retrieves from mental_health_diagnostic_support and checks symptoms
Returns: detected_disease, diagnostic_confidence (0-1)
"""
import json
import logging
from typing import Dict, Any

from ..state import KGState
from src.rag.retrieval.dense_retrieval import DenseRetrieval
from src.rag.llm.llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Initialize diagnostic retrieval
diagnostic_retrieval = DenseRetrieval(collection_name="mental_health_diagnostic_support")


async def diagnostic_check_node(state: KGState) -> KGState:
    """
    Check symptoms against diagnostic knowledge base
    
    Args:
        state: KGState with rewritten_query, slots, conversation_buffer, summary_context
    
    Returns:
        Updated state with diagnostic_chunks, detected_disease, diagnostic_confidence, diagnostic_reasoning
    """
    rewritten_query = state.get("rewritten_query", state.get("question", ""))
    slots = state.get("slots", {})
    conversation_buffer = state.get("conversation_buffer", [])
    summary_context = state.get("summary_context", "")
    
    logger.info(f"🔬 Starting diagnostic check with query: {rewritten_query}")
    
    try:
        # Retrieve from diagnostic collection
        diagnostic_results = await diagnostic_retrieval.retrieve_async(rewritten_query, top_k=5)
        diagnostic_chunks_text = diagnostic_results.context
        
        logger.info(f"Retrieved diagnostic context (length: {len(diagnostic_chunks_text)})")
        
        # Load diagnostic check prompt
        prompt_templates = await load_prompts("diagnostic_check_prompt.yaml")
        system_prompt = prompt_templates.get("system", "")
        user_prompt_template = prompt_templates.get("user", "")
        
        # Format conversation history
        conversation_history = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
            for msg in conversation_buffer[-5:]
        ]) if conversation_buffer else "Không có lịch sử hội thoại"
        
        # Format user prompt
        user_prompt = user_prompt_template.format(
            query=rewritten_query,
            slots=json.dumps(slots, ensure_ascii=False, indent=2),
            conversation_history=conversation_history,
            summary=summary_context or "Không có tóm tắt",
            diagnostic_chunks=diagnostic_chunks_text
        )
        
        # Call LLM for diagnostic analysis
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        import asyncio
        loop = asyncio.get_event_loop()
        response_content = await loop.run_in_executor(None, lambda: llm.invoke(full_prompt, max_retries=3))
        
        logger.debug(f"Diagnostic LLM response: {response_content}")
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
            detected_disease = result.get("disease", "")
            confidence = float(result.get("confidence", 0.0))
            reasoning = result.get("reasoning", "")
            
            logger.info(f"✅ Diagnostic check: disease='{detected_disease}', confidence={confidence:.2f}")
            
            state["diagnostic_chunks"] = diagnostic_chunks_text
            state["detected_disease"] = detected_disease
            state["diagnostic_confidence"] = confidence
            state["diagnostic_reasoning"] = reasoning
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse diagnostic response: {e}")
            logger.error(f"Response content: {response_content}")
            state["diagnostic_chunks"] = diagnostic_chunks_text
            state["detected_disease"] = ""
            state["diagnostic_confidence"] = 0.0
            state["diagnostic_reasoning"] = "Không thể phân tích kết quả"
        
    except Exception as e:
        logger.error(f"Error in diagnostic check: {e}", exc_info=True)
        state["diagnostic_chunks"] = ""
        state["detected_disease"] = ""
        state["diagnostic_confidence"] = 0.0
        state["diagnostic_reasoning"] = f"Lỗi: {str(e)}"
    
    return state

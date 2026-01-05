"""
Disease Conclusion LLM Node
Analyzes diagnostic chunks and concludes disease diagnosis
"""
import json
import logging
from typing import Dict, Any, Tuple

from ..llm_gemini import llm
from ...prompts.loader import load_prompts

logger = logging.getLogger(__name__)


def analyze_disease(
    diagnostic_chunks: str,
    rewritten_query: str,
    slots: Dict[str, Any],
    conversation_buffer: list,
    summary_context: str
) -> Tuple[str, float, str, str, str, str]:
    """
    Analyze diagnostic chunks and conclude disease using LLM
    
    Args:
        diagnostic_chunks: Retrieved diagnostic knowledge
        rewritten_query: User's rewritten query
        slots: Extracted symptom slots
        conversation_buffer: Conversation history
        summary_context: Summary of conversation
    
    Returns:
        Tuple of (disease_name, confidence, reasoning, disease_description, disease_symptoms, disease_causes)
    """
    logger.info(f"🧠 Analyzing disease from diagnostic chunks")
    
    try:
        # Load diagnostic check prompt
        prompt_templates = load_prompts("diagnostic_check_prompt.yaml")
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
            diagnostic_chunks=diagnostic_chunks
        )
        
        # Call LLM for diagnostic analysis
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response_content = llm.invoke(full_prompt, max_retries=3)
        
        logger.debug(f"Diagnostic LLM response: {response_content}")
        
        # Strip markdown code fence if present (```json ... ```)
        response_content = response_content.strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:]  # Remove ```json
        if response_content.startswith("```"):
            response_content = response_content[3:]  # Remove ```
        if response_content.endswith("```"):
            response_content = response_content[:-3]  # Remove ```
        response_content = response_content.strip()
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
            detected_disease = result.get("disease", "")
            confidence = float(result.get("confidence", 0.0))
            reasoning = result.get("reasoning", "")
            disease_description = result.get("disease_description", "")
            disease_symptoms = result.get("disease_symptoms", "")
            disease_causes = result.get("disease_causes", "")
            
            logger.info(f"✅ Disease analysis: disease='{detected_disease}', confidence={confidence:.2f}")
            
            return detected_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse diagnostic response: {e}")
            logger.error(f"Response content: {response_content}")
            return "", 0.0, "Không thể phân tích kết quả", "", "", ""
        
    except Exception as e:
        logger.error(f"❌ Error in disease analysis: {e}", exc_info=True)
        return "", 0.0, f"Lỗi: {str(e)}", "", "", ""

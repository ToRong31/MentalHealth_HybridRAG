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
        
        # Try to extract JSON from response (in case LLM adds extra text)
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
        if json_match:
            response_content = json_match.group(0)
            logger.debug(f"Extracted JSON: {response_content}")
        
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
            raise ValueError(f"Failed to parse LLM diagnostic response: {e}")
        
    except ValueError as e:
        # Re-raise ValueError from parsing
        logger.error(f"❌ ValueError in disease analysis: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error in disease analysis: {e}", exc_info=True)
        raise


def evaluate_all_diseases(
    diagnostic_diseases: list,
    diagnostic_chunks: str,
    rewritten_query: str,
    slots: Dict[str, Any],
    conversation_buffer: list,
    summary_context: str
) -> Tuple[str, float, str, str, str, str]:
    """
    Evaluate confidence for ALL diseases from retrieval and return the best match
    
    Args:
        diagnostic_diseases: List of diseases from retrieval
        diagnostic_chunks: Retrieved diagnostic knowledge
        rewritten_query: User's rewritten query
        slots: Extracted symptom slots
        conversation_buffer: Conversation history
        summary_context: Summary of conversation
    
    Returns:
        Tuple of (best_disease, confidence, reasoning, description, symptoms, causes)
    """
    logger.info(f"🎯 Evaluating confidence for {len(diagnostic_diseases)} diseases: {diagnostic_diseases}")
    
    if not diagnostic_diseases:
        return "", 0.0, "No diseases to evaluate", "", "", ""
    
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
        
        # Format user prompt with all parameters
        user_prompt = user_prompt_template.format(
            query=rewritten_query,
            slots=json.dumps(slots, ensure_ascii=False, indent=2),
            conversation_history=conversation_history,
            summary=summary_context or "Không có tóm tắt",
            diagnostic_chunks=diagnostic_chunks
        )
        
        # Call LLM for evaluation
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response_content = llm.invoke(full_prompt, max_retries=3)
        
        logger.debug(f"All diseases evaluation response: {response_content}")
        
        # Strip markdown code fence if present
        response_content = response_content.strip()
        if response_content.startswith("```json"):
            response_content = response_content[7:]
        if response_content.startswith("```"):
            response_content = response_content[3:]
        if response_content.endswith("```"):
            response_content = response_content[:-3]
        response_content = response_content.strip()
        
        # Try to extract JSON from response (in case LLM adds extra text)
        # Look for JSON object between { and }
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_content, re.DOTALL)
        if json_match:
            response_content = json_match.group(0)
            logger.debug(f"Extracted JSON: {response_content}")
        
        # Parse JSON response
        try:
            result = json.loads(response_content)
            best_disease = result.get("disease", "")
            confidence = float(result.get("confidence", 0.0))
            reasoning = result.get("reasoning", "")
            disease_description = result.get("disease_description", "")
            disease_symptoms = result.get("disease_symptoms", "")
            disease_causes = result.get("disease_causes", "")
            
            logger.info(f"✅ Best disease: '{best_disease}' with confidence={confidence:.2f}")
            logger.info(f"📊 Reasoning: {reasoning}")
            
            return best_disease, confidence, reasoning, disease_description, disease_symptoms, disease_causes
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse evaluation response: {e}")
            logger.error(f"Response content: {response_content}")
            raise ValueError(f"Failed to parse LLM evaluation response: {e}")
        
    except ValueError as e:
        # Re-raise ValueError from parsing
        logger.error(f"❌ ValueError evaluating diseases: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error evaluating all diseases: {e}", exc_info=True)
        raise

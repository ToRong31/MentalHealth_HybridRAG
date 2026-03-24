"""
Personal/Theoretical Classifier and Treatment Confirmation Classifier
Classify query nature: personal (about user's own situation) or theoretical (general knowledge)
Classify treatment confirmation: wants_treatment or doesnt_want_treatment
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts, format_prompt

logger = logging.getLogger(__name__)

# Load router prompts
try:
    router_prompt_data = load_prompts("router_prompts.yaml")
    router_prompt_template = router_prompt_data.get("router_prompt", "")
except Exception as e:
    logger.error(f"Failed to load router prompts: {e}")
    router_prompt_template = ""


async def router(
    question: str,
    query_type: str = None,
    conversation_buffer: list = None,
    summary_context: str = "",
    awaiting_treatment_confirmation: bool = False,
    detected_disease: str = ""
) -> Dict[str, Any]:
    """
    Router function that handles multiple classification tasks:
    1. If awaiting_treatment_confirmation=True: Classify if user wants treatment
    2. Otherwise: Classify query nature (personal or theoretical)
    
    Args:
        question: User question or response
        query_type: Type from query_classifier (follow_up, topic_change, off_topic)
        conversation_buffer: Conversation history buffer
        summary_context: Summary of conversation
        awaiting_treatment_confirmation: If True, classify treatment confirmation
        detected_disease: Disease name (for treatment confirmation)
    
    Returns:
        Dict with query_nature/wants_treatment and reasoning
    """
    if conversation_buffer is None:
        conversation_buffer = []
    
    # Build conversation context from buffer + summary
    from src.rag.utils.memory import format_buffer_for_context, format_summary_context
    
    buffer_text = format_buffer_for_context(conversation_buffer)
    summary_text = format_summary_context(summary_context)
    
    conversation_context_parts = []
    if summary_text:
        conversation_context_parts.append(f"Summary of previous conversation:\n{summary_text}")
    if buffer_text:
        conversation_context_parts.append(f"Recent conversation:\n{buffer_text}")
    
    conversation_context = "\n\n".join(conversation_context_parts) if conversation_context_parts else "No previous conversation."
    
    # Determine which classification to perform
    if awaiting_treatment_confirmation:
        # Treatment confirmation classification
        if not router_prompt_template:
            logger.error("Router prompt is empty!")
            return {
                "wants_treatment": False,
                "reasoning": "Default to doesn't want due to missing prompt"
            }
        
        prompt = format_prompt(
            router_prompt_template,
            QUESTION=question,
            ROUTING_MODE="treatment_confirmation",
            CONVERSATION_CONTEXT=conversation_context,
            QUERY_TYPE="",
            DETECTED_DISEASE=detected_disease or "Unknown"
        )
        
        logger.info(f"Treatment confirmation classifier prompt length: {len(prompt)}")
        logger.debug(f"Classifying treatment confirmation: {question[:50]}...")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: llm.invoke(prompt, max_retries=3)
            )
            
            json_match = re.search(
                r'\{[^{}]*"wants_treatment"[^{}]*\}',
                response,
                re.DOTALL
            )
            
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                
                wants_treatment = result.get("wants_treatment", False)
                reasoning = result.get("reasoning", "")
                
                if not isinstance(wants_treatment, bool):
                    wants_treatment = str(wants_treatment).lower() in ['true', '1', 'yes']
                
                logger.info(f"Treatment confirmation: wants_treatment={wants_treatment} - {reasoning}")
                
                return {
                    "wants_treatment": wants_treatment,
                    "reasoning": reasoning
                }
            else:
                logger.warning(f"Could not parse JSON from LLM response: {response}")
                return {
                    "wants_treatment": False,
                    "reasoning": "Could not parse LLM response, defaulting to doesn't want"
                }
        except Exception as e:
            logger.error(f"Error in treatment confirmation classification: {e}", exc_info=True)
            return {
                "wants_treatment": False,
                "reasoning": f"Error occurred: {str(e)}, defaulting to doesn't want"
            }
    
    else:
        # Personal/Theoretical classification
        if not router_prompt_template:
            logger.error("Router prompt is empty!")
            return {
                "query_nature": "personal",
                "reasoning": "Default to personal due to missing prompt"
            }
        
        prompt = format_prompt(
            router_prompt_template,
            QUESTION=question,
            ROUTING_MODE="query_nature",
            QUERY_TYPE=query_type or "follow_up",
            CONVERSATION_CONTEXT=conversation_context,
            DETECTED_DISEASE=""
        )
        
        logger.info(f"Personal/theoretical classifier prompt length: {len(prompt)}")
        logger.debug(f"Classifying query nature: {question[:50]}...")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: llm.invoke(prompt, max_retries=3)
            )
            
            json_match = re.search(
                r'\{[^{}]*"query_nature"[^{}]*\}',
                response,
                re.DOTALL
            )
            
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                
                query_nature = result.get("query_nature", "personal")
                reasoning = result.get("reasoning", "")
                
                if query_nature not in ["personal", "theoretical"]:
                    logger.warning(f"Invalid query_nature '{query_nature}', defaulting to 'personal'")
                    query_nature = "personal"
                
                logger.info(f"Query nature classified as: {query_nature} - {reasoning}")
                
                return {
                    "query_nature": query_nature,
                    "reasoning": reasoning
                }
            else:
                logger.warning(f"Could not parse JSON from LLM response: {response}")
                return {
                    "query_nature": "personal",
                    "reasoning": "Could not parse LLM response, defaulting to personal"
                }
        except Exception as e:
            logger.error(f"Error in personal/theoretical classification: {e}", exc_info=True)
            return {
                "query_nature": "personal",
                "reasoning": f"Error occurred: {str(e)}, defaulting to personal"
            }



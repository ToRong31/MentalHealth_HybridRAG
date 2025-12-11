"""
Answer with Hybrid Node
Sinh câu trả lời dựa trên cả graph context và document context
"""
import logging
from typing import Dict, Any

from ..llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load fallback answer
try:
    response_templates = load_prompts("response_templates.yaml")
    fallback_answer_hybrid = response_templates.get("fallback_answer_hybrid", "")
except Exception as e:
    logger.error(f"Failed to load fallback answer: {e}")
    fallback_answer_hybrid = """I'm having technical issues. Could you tell me more about what you're experiencing?"""


def answer_with_hybrid_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sinh câu trả lời dựa trên cả graph context và document context
    
    Args:
        state: State dict với 'question', 'graph_context', 'doc_context'
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    q = state["question"]
    graph_context = state.get("graph_context", "")
    doc_context = state.get("doc_context", "")
    
    # Load appropriate prompt based on user language
    if state.get("user_language") == "vi":
        try:
            answer_prompt_data = load_prompts("answer_nodes_prompt_vie.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
        except Exception as e:
            logger.warning(f"Failed to load Vietnamese prompt: {e}, using English version...")
            answer_prompt_data = load_prompts("answer_nodes_prompt_en.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
    else:
        answer_prompt_data = load_prompts("answer_nodes_prompt_en.yaml")
        system_instructions = answer_prompt_data.get("system_instructions", "")
        user_template = answer_prompt_data.get("user_template", "")
    
    try:
        # Combine contexts
        combined_context = f"""
From Knowledge Graph:
{graph_context if graph_context else "(No graph knowledge available)"}

From Documents:
{doc_context if doc_context else "(No document knowledge available)"}
""".strip()
        
        # Build full prompt
        user_message = user_template.replace("{{QUESTION}}", q).replace(
            "{{GRAPH_CONTEXT}}",
            combined_context
        )
        
        full_prompt = f"{system_instructions}\n\n{user_message}"
        
        # Generate answer with retry
        answer = llm.invoke(full_prompt, max_retries=3)
        
    except Exception as e:
        # Fallback answer khi LLM fail
        logger.error(f"Failed to generate answer: {e}")
        answer = fallback_answer_hybrid
    
    state["answer"] = answer
    state["done"] = True
    
    return state

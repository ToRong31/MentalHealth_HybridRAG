"""
Answer Generation Nodes
LangGraph nodes để sinh câu trả lời dựa trên context
"""
import json
import re
import logging
from typing import Dict, Any

from .llm_gemini import llm
from src.rag.prompts.loader import load_prompts

logger = logging.getLogger(__name__)

# Load safety check prompt
safety_check_prompt_data = load_prompts("safety_check_prompt.yaml")
safety_check_prompt = safety_check_prompt_data.get("safety_check_prompt", "")



if not safety_check_prompt:
    raise ValueError("Safety check prompt is empty! Check safety_check_prompt.yaml file.")

# Load response templates (Vietnamese)
try:
    response_templates = load_prompts("response_templates.yaml")
    crisis_response = response_templates.get("crisis_response", "")
    not_mental_health_response = response_templates.get("not_mental_health_response", "")
    fallback_answer = response_templates.get("fallback_answer", "")
    fallback_answer_hybrid = response_templates.get("fallback_answer_hybrid", "")
    
    if not crisis_response or not not_mental_health_response:
        raise ValueError("Missing required response templates")
    
    logger.info("Successfully loaded Vietnamese response templates")
except Exception as e:
    logger.error(f"Failed to load response_templates.yaml: {e}")
    # English fallback
    crisis_response = """I hear that you're in a lot of pain right now. Please reach out to crisis services immediately: 988 (US), 115 (Vietnam), or your local emergency services."""
    not_mental_health_response = """Thank you for your question. I'm specifically trained to help with mental health concerns. Your question seems outside my expertise."""
    fallback_answer = """I'm having technical difficulties. Could you share more about your situation?"""
    fallback_answer_hybrid = """I'm having technical issues. Could you tell me more about what you're experiencing?"""
    logger.warning("Using English fallback responses")

# Load therapist prompt (Vietnamese version preferred)


try:
    response_templates_dense = load_prompts("answer_dense_promt_vie.yaml")
    system_instructions_dense = response_templates_dense.get("system_instructions", "")
    user_template_dense = response_templates_dense.get("user_template", "")
    
    if not user_template_dense:
        raise ValueError("Missing user_template in answer_dense_promt.yaml")
    logger.info("Successfully loaded answer_dense_promt.yaml")
except Exception as e:
    logger.error(f"Failed to load answer_dense_promt.yaml: {e}") # Fallback to previous template

def safety_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kiểm tra xem câu hỏi có liên quan đến mental health và có phải high-risk không.
    
    Args:
        state: State dict với 'question' key
    
    Returns:
        Updated state với 'is_mental_health_related' và 'is_high_risk'
    """
    q = state["question"]
    
    # Validate prompt
    if not safety_check_prompt:
        logger.error("Safety check prompt is empty!")
        raise ValueError("Safety check prompt is not loaded properly")
    
    # Tạo prompt với câu hỏi của user
    prompt = safety_check_prompt.replace("{{QUESTION}}", q)
    
    logger.info(f"Safety check prompt length: {len(prompt)}")
    
    # Gọi LLM để phân tích
    try:
        response = llm.invoke(prompt)
        
        # Parse JSON response
        # Tìm JSON trong response (phòng trường hợp LLM trả về text thêm)
        json_match = re.search(
            r'\{[^{}]*"is_mental_health_related"[^{}]*\}',
            response,
            re.DOTALL
        )
        
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            state["is_mental_health_related"] = result.get(
                "is_mental_health_related",
                True
            )
            state["is_high_risk"] = result.get("is_high_risk", False)
        else:
            # Fallback: nếu không parse được JSON, mặc định là mental health related
            print(f"Warning: Could not parse JSON from LLM response: {response}")
            state["is_mental_health_related"] = True
            state["is_high_risk"] = False
            
    except Exception as e:
        print(f"Error in safety_check_node: {e}")
        # Fallback an toàn: cho phép tiếp tục
        state["is_mental_health_related"] = True
        state["is_high_risk"] = False
    
    return state


def crisis_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trả về thông báo khẩn cấp cho các trường hợp high-risk.
    
    Args:
        state: State dict
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    state["answer"] = crisis_response
    state["skip_translation"] = True  # response already in user-facing language
    state["done"] = True
    return state


def not_mental_health_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trả về thông báo chỉ hỗ trợ mental health cho các câu hỏi không liên quan.
    
    Args:
        state: State dict
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    state["answer"] = not_mental_health_response
    state["skip_translation"] = True  # response already in user-facing language
    state["done"] = True
    return state


def answer_with_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    if(state["user_language"] == "vi"):
        try:

            answer_prompt_data = load_prompts("answer_nodes_prompt_vie.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
            
            if not system_instructions or not user_template:
                raise ValueError("Missing system_instructions or user_template")
            
            logger.info("Successfully loaded Vietnamese therapist prompt")
        except Exception as e:
            logger.warning(f"Failed to load Vietnamese prompt: {e}, trying English version...")
    else:
        try:
            answer_prompt_data = load_prompts("answer_nodes_prompt_en.yaml")
            system_instructions = answer_prompt_data.get("system_instructions", "")
            user_template = answer_prompt_data.get("user_template", "")
            
            if not system_instructions or not user_template:
                raise ValueError("Missing system_instructions or user_template")
            
            logger.info("Successfully loaded English therapist prompt")
        except Exception as e:
            logger.error(f"Failed to load English prompt: {e}")
            raise RuntimeError(f"Cannot load any therapist prompt files: {e}")
        """
    Sinh câu trả lời dựa trên graph context
    
    Args:
        state: State dict với 'question' và 'graph_context'
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    q = state["question"]
    graph_context = state.get("graph_context", "")
    
    try:
        # Build full prompt with system instructions + user message
        user_message = user_template.replace("{{QUESTION}}", q).replace(
            "{{GRAPH_CONTEXT}}",
            graph_context if graph_context else "No specific knowledge available."
        )
        
        # Combine system instructions with user message
        full_prompt = f"{system_instructions}\n\n{user_message}"
        
        # Generate answer with retry
        answer = llm.invoke(full_prompt, max_retries=3)
        
    except Exception as e:
        # Fallback answer khi LLM fail (Vietnamese)
        logger.error(f"Failed to generate answer: {e}")
        answer = fallback_answer
    
    state["answer"] = answer
    state["done"] = True
    
    return state

def answer_with_dense_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sinh câu trả lời dựa trên document context từ dense retrieval
    
    Args:
        state: State dict với 'question' và 'doc_context'
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    q = state["question"]
    dense_context = state.get("dense_context", "")
    
    try:
        # Build full prompt
        user_message = user_template_dense.replace("{{PATIENT_INPUT}}", q).replace(
            "{{DOCTOR_DIALOGUE}}",
            dense_context if dense_context else "No specific knowledge available."
        )
        
        full_prompt = f"{system_instructions_dense}\n\n{user_message}"
        
        # Generate answer with retry
        answer = llm.invoke(full_prompt, max_retries=3)
        
    except Exception as e:
        # Fallback answer khi LLM fail (Vietnamese)
        logger.error(f"Failed to generate answer: {e}")
        answer = fallback_answer
    
    state["answer"] = answer
    state["done"] = True
    
    return state

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
        # Fallback answer khi LLM fail (Vietnamese)
        logger.error(f"Failed to generate answer: {e}")
        answer = fallback_answer_hybrid
    
    state["answer"] = answer
    state["done"] = True
    
    return state


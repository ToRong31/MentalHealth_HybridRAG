"""
Answer Generation Nodes
LangGraph nodes để sinh câu trả lời dựa trên context
"""
import json
import re
from typing import Dict, Any

from .llm_gemini import llm
from src.prompts import (
    therapist_prompt,
    safety_check_prompt,
    crisis_response,
    not_mental_health_response
)


def safety_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kiểm tra xem câu hỏi có liên quan đến mental health và có phải high-risk không.
    
    Args:
        state: State dict với 'question' key
    
    Returns:
        Updated state với 'is_mental_health_related' và 'is_high_risk'
    """
    q = state["question"]
    
    # Tạo prompt với câu hỏi của user
    prompt = safety_check_prompt.replace("{{QUESTION}}", q)
    
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
    state["done"] = True
    return state


def answer_with_graph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sinh câu trả lời dựa trên graph context
    
    Args:
        state: State dict với 'question' và 'graph_context'
    
    Returns:
        Updated state với 'answer' và 'done' = True
    """
    q = state["question"]
    graph_context = state.get("graph_context", "")
    
    # Format prompt
    prompt = therapist_prompt.replace("{{QUESTION}}", q).replace(
        "{{GRAPH_CONTEXT}}",
        graph_context
    )
    
    # Generate answer
    answer = llm.invoke(prompt)
    
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
    
    # Combine contexts
    combined_context = f"""
Graph Knowledge:
{graph_context}

Document Knowledge:
{doc_context}
""".strip()
    
    # Format prompt
    prompt = therapist_prompt.replace("{{QUESTION}}", q).replace(
        "{{GRAPH_CONTEXT}}",
        combined_context
    )
    
    # Generate answer
    answer = llm.invoke(prompt)
    
    state["answer"] = answer
    state["done"] = True
    
    return state


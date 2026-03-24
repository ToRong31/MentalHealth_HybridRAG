"""
Prompts Module
Load và manage prompts từ YAML files
"""
from .loader import load_prompts, format_prompt

# Load prompts at module level
_prompts = load_prompts()

therapist_prompt = _prompts.get('therapist_prompt', '')
safety_check_prompt = _prompts.get('safety_check_prompt', '')
crisis_response = _prompts.get('crisis_response', 'Please seek immediate help.')
not_mental_health_response = _prompts.get(
    'not_mental_health_response',
    'I can only help with mental health questions.'
)

__all__ = [
    'load_prompts',
    'format_prompt',
    'therapist_prompt',
    'safety_check_prompt',
    'crisis_response',
    'not_mental_health_response',
]

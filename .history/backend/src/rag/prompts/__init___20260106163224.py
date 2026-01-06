"""
Prompts Module
Load và manage prompts từ YAML files
"""
from .loader import load_prompts, format_prompt

# Note: load_prompts is now async. 
# The old module-level loading has been removed to avoid blocking I/O.
# Users should call 'await load_prompts()' directly in their async functions.

__all__ = [
    'load_prompts',
    'format_prompt',
]

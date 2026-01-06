"""
Prompt Loader Module
Load và format prompts từ YAML files
"""
import os
import yaml
import aiofiles
from pathlib import Path
from typing import Dict, Any, Union


def load_prompts(filename: str = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Load prompts from YAML files
    
    Args:
        filename: Optional specific file to load (e.g., "therapist_prompt.yaml")
                 If None, loads all prompts
    
    Returns:
        If filename specified: Dictionary with prompt data from that file
        If filename not specified: Dictionary with all prompt names and content
    """
    prompts_dir = Path(__file__).parent
    
    # If specific file requested, load just that file
    if filename:
        filepath = prompts_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Prompt file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if data else {}
    
    # Otherwise, load all prompts
    prompts = {}
    
    # Load therapist prompt
    therapist_file = prompts_dir / "therapist_prompt.yaml"
    if therapist_file.exists():
        with open(therapist_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            prompts['therapist_prompt'] = data.get('prompt', '')
    
    # Load safety check prompt
    safety_file = prompts_dir / "safety_check_prompt.yaml"
    if safety_file.exists():
        with open(safety_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            prompts['safety_check_prompt'] = data.get('prompt', '')
            prompts['crisis_response'] = data.get('crisis_response', '')
            prompts['not_mental_health_response'] = data.get('not_mental_health_response', '')
    
    return prompts


def format_prompt(template: str, **kwargs) -> str:
    """
    Format prompt template with variables
    
    Args:
        template: Prompt template with {{VAR}} placeholders
        **kwargs: Variable values
    
    Returns:
        Formatted prompt
    """
    result = template
    for key, value in kwargs.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    
    return result

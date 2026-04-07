"""
Shared YAML prompt loader.
Loads skill prompts from ai/agents/*/skills/prompts/*.yaml files.

Each YAML file contains:
  name: str          — skill name
  description: str   — one-line description
  system: str        — system prompt for the skill
  examples: list      — few-shot examples

Usage:
    from ai.shared.prompts import load_prompt, load_prompt_meta

    # Get system prompt only
    system = load_prompt("diagnostic.skills.clinical_reasoning")

    # Get full metadata (name + description + system + examples)
    meta = load_prompt_meta("diagnostic.skills.clinical_reasoning")
    print(meta["name"])        # "clinical_reasoning"
    print(meta["description"]) # "LLM-driven DSM-5 diagnostic evaluation"
    print(meta["system"])     # full system prompt
    print(meta["examples"])     # list of examples
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Path to the ai/ directory root
_AI_ROOT = Path(__file__).parent.parent / "agents"


def _load_yaml(relative_path: str) -> dict[str, Any]:
    """Load a YAML file relative to the ai/agents/ directory."""
    path = _AI_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt_meta(qualname: str) -> dict[str, Any]:
    """
    Load full prompt metadata from a YAML file.

    Args:
        qualname: Dot-separated path within ai/agents/, without .yaml extension.
                  E.g. "diagnostic.skills.clinical_reasoning"
                       "support.skills.emotional_support"

    Returns:
        {
            "name": str,
            "description": str,
            "system": str,
            "examples": list[dict],
        }

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        KeyError: If required keys are missing.
    """
    path = Path(qualname.replace(".", "/"))
    yaml_path = f"{path}.yaml"
    data = _load_yaml(yaml_path)

    required = ("name", "description", "system")
    for key in required:
        if key not in data:
            raise KeyError(f"'{key}' key not found in {yaml_path}")

    return {
        "name": data["name"],
        "description": data["description"],
        "system": data["system"],
        "examples": data.get("examples", []),
    }


def load_prompt(qualname: str) -> str:
    """
    Load system prompt string from a YAML file.

    Args:
        qualname: Dot-separated path within ai/agents/, without .yaml extension.
                  E.g. "diagnostic.skills.clinical_reasoning"
                       "support.skills.emotional_support"

    Returns:
        The system prompt string.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        KeyError: If the 'system' key is missing.
    """
    meta = load_prompt_meta(qualname)
    return meta["system"]
